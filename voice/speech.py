import speech_recognition as sr
import logging
import os
import time
import sys
import io
import numpy as np
import threading
import flet as ft
from pathlib import Path
import uuid
from datetime import datetime, timezone
from typing import Callable

from dotenv import load_dotenv
load_dotenv()

from voice.interact_app import translation_tasks
from voice.utils.json_utils import save_text
from voice.utils.asr_metrics import analyze_transcription, success_rate
from voice.utils.metrics_storage import (
    create_session,
    save_transcription_result,
    save_command_result,
    flush_offline_queue,
)
from constant import ASR_MODEL_KEY


logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO,
                    encoding="utf-8",
                    handlers=[logging.FileHandler("voice.log", encoding="utf-8"),
                              logging.StreamHandler(sys.stdout)])


_Transcriber = Callable[[bytes], tuple[str, list, float | None]]

def ask_user_feedback() -> bool:
        """
        Pede o input do usuário via terminal e retorna True para 'sim' e False para 'não'.
        """
        while True:
            # Pega o input, remove espaços em branco nas pontas e joga para minúsculas
            resposta = input("O reconhecimento foi correto? (sim/não): ").strip().lower()
            
            # Aceita variações comuns de "sim"
            if resposta in ['sim', 's', 'yes', 'y']:
                return True
            # Aceita variações comuns de "não"
            elif resposta in ['não', 'nao', 'n', 'no']:
                return False
            else:
                # Se digitar algo diferente, o loop repete a pergunta
                print("⚠️ Entrada inválida. Por favor, responda apenas com 'sim' ou 'não'.")

def _parse_model_key(model_key: str) -> tuple[str, str]:
    """Separa 'backend:model_name' → ('backend', 'model_name')."""
    if ":" not in model_key:
        raise ValueError(f"model_key inválido: '{model_key}'. Use o formato 'backend:model_name'.")
    backend, model_name = model_key.split(":", 1)
    return backend.strip(), model_name.strip()


def _load_faster_whisper(model_name: str) -> _Transcriber:
    """CTranslate2 + CUDA float16.
    Único backend com word-level timestamps → métrica avg_confidence disponível.
    """
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cuda", compute_type="float16")

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        segments, info = model.transcribe(
            io.BytesIO(wav_bytes), beam_size=5, language="pt", word_timestamps=True
        )
        segments = list(segments)
        text = "".join(s.text for s in segments).strip()
        return text, segments, getattr(info, "duration", None)

    return _transcribe


def _make_nemo_transcriber(model: str) -> _Transcriber:
    """Factory compartilhada pelos backends NeMo (Canary, Parakeet).
    NeMo.transcribe() exige caminhos de arquivo; áudio é salvo em temp file.
    """
    import os
    import tempfile
    import torch
    import soundfile as sf

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, 16000)
            tmp_path = f.name

        try:
            with torch.autocast("cuda", dtype=torch.float16):
                output = model.transcribe([tmp_path], source_lang="pt", target_lang="pt", num_workers=0, batch_size=1)
            result = output[0] if output else ""
            # NeMo pode retornar str ou Hypothesis (com atributo .text)
            text = (result.text if hasattr(result, "text") else str(result)).strip()
            # Hypothesis contém tensores GPU (logprobs, scores). Se o GC liberar
            # esses tensores durante a próxima inferência → illegal memory access.
            # Forçar liberação imediata e sincronizar antes de retornar.
            del output, result
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
        finally:
            os.unlink(tmp_path)

        return text, [], duration

    return _transcribe


def _log_decoding_diagnostics(model, label: str) -> None:
    """DEBUG temporário: revela se a decodificação greedy usa CUDA Graphs.
    Necessário para investigar illegal memory access no Parakeet (crash na 2ª
    inferência) — modelos RNNT/TDT capturam o decoder greedy como CUDA Graph
    em versões recentes do NeMo, o que pode quebrar ao trocar o shape do input
    entre chamadas. Remover após identificar a causa raiz.
    """
    try:
        logging.info(f"[{label}] decoding cfg: {getattr(model.cfg, 'decoding', None)}")
    except Exception:
        logging.exception(f"[{label}] Falha ao ler model.cfg.decoding")

    decoding_obj = getattr(model, "decoding", None)
    inner = getattr(decoding_obj, "decoding", None) if decoding_obj is not None else None
    for obj, obj_name in ((decoding_obj, "decoding"), (inner, "decoding.decoding")):
        if obj is None:
            continue
        graph_attrs = [a for a in dir(obj) if "graph" in a.lower() and not a.startswith("__")]
        logging.info(f"[{label}] {obj_name} class={type(obj).__name__} atributos-cuda-graph={graph_attrs}")
        for attr in graph_attrs:
            try:
                logging.info(f"[{label}] {obj_name}.{attr} = {getattr(obj, attr)}")
            except Exception:
                logging.info(f"[{label}] {obj_name}.{attr} = <erro ao ler>")


def _apply_gpu_optimizations() -> None:
    import torch
    # TF32: Ampere (RTX 30xx) executa matmuls em TF32 internamente mantendo float32 na API.
    # Reduz precisão de 23 para 10 bits mantendo a mesma velocidade de float16.
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    # cuDNN escolhe automaticamente o algoritmo mais rápido para cada shape de input.
    torch.backends.cudnn.benchmark = True


def _load_canary(model_name: str) -> _Transcriber:
    """NVIDIA Canary via NeMo — encoder-decoder multilingual (en/de/fr/es).
    Requer: pip install 'nemo_toolkit[asr]'
    """
    import nemo.collections.asr as nemo_asr

    _apply_gpu_optimizations()
    model = nemo_asr.models.ASRModel.from_pretrained(model_name="nvidia/canary-1b-v2")
    model = model.cuda()
    _log_decoding_diagnostics(model, "canary-v2")
    return _make_nemo_transcriber(model)


def _load_parakeet(model_name: str) -> _Transcriber:
    """NVIDIA Parakeet via NeMo — modelo CTC/TDT compacto (inglês).
    Requer: pip install 'nemo_toolkit[asr]'
    """
    from nemo.collections.asr.models import ASRModel

    _apply_gpu_optimizations()
    model = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v3")
    model = model.cuda()
    _log_decoding_diagnostics(model, "parakeet-v3")
    return _make_nemo_transcriber(model)


def _load_voxtral(model_name: str) -> _Transcriber:
    """Mistral Voxtral via transformers — LLM causal multimodal com entrada de áudio.
    Requer: pip install transformers 'mistral-common[audio]'
    """
    import torch
    from transformers import AutoProcessor, AutoModelForCausalLM

    repo_id = "mistralai/Voxtral-Mini-4B-Realtime-2602"

    processor = AutoProcessor.from_pretrained(repo_id)
    model = AutoModelForCausalLM.from_pretrained(
        repo_id, device_map="auto", torch_dtype=torch.float16
    )
    model.eval()

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0

        inputs = processor(
            text="Transcribe the following audio:",
            audios=[audio],
            sampling_rate=16000,
            return_tensors="pt",
        ).to("cuda")

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=512)

        # Remove tokens de entrada; decodifica apenas o trecho gerado
        input_len = inputs["input_ids"].shape[1]
        text = processor.decode(output_ids[0, input_len:], skip_special_tokens=True).strip()
        return text, [], duration

    return _transcribe


_BACKEND_LOADERS: dict[str, Callable[[str], _Transcriber]] = {
    "faster-whisper": _load_faster_whisper,
    "canary-v2": _load_canary,
    "parakeet-v3": _load_parakeet,
    "voxtral-mini": _load_voxtral,
}


class SpeechToText:
    _model_cache: dict[str, _Transcriber] = {}
    _model_events: dict[str, threading.Event] = {}
    _model_load_times: dict[str, float] = {}
    _model_load_lock = threading.Lock()

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.is_recording = False
        self.stop_listening = None

        self._current_model_key = ASR_MODEL_KEY
        self._feedback_history: list[bool] = []
        self._last_metrics: dict = {}
        self._last_transcription: str | None = None
        self._transcriber: _Transcriber | None = None

        self._stop_requested: bool = False
        self._collected_texts: list[str] = []
        self._stop_event: threading.Event = threading.Event()
        self._last_audio_time: float = 0.0
        self._startup_start_time: float | None = None

        self.load_model(ASR_MODEL_KEY)

        self.metrics_session_id = create_session(
            member_name=os.getenv("MEMBER_NAME", "anonimo"),
            model_name=self._current_model_key,
            model_source="huggingface",
            scenario="dictation",
        )
        flush_offline_queue()

    # Benchmark

    def run_benchmark(self, audio, reference):
        self._recognize_and_measure(audio, reference)
        #sr = ask_user_feedback()
        self.record_feedback(True)

    def run_benchmark_transcription(self, audio, reference):
        self._recognize_and_measure(audio, reference)
        entry = self._build_metrics_entry(ok=False)
        save_transcription_result(entry)

    # ── Feedback ────────────────────────────────────────────────────────────────

    def record_feedback(self, ok: bool) -> None:
        self._feedback_history.append(ok)
        self._log_feedback(ok)
        entry = self._build_metrics_entry(ok)
        self._persist_metrics(entry)

    def _log_feedback(self, ok: bool) -> None:
        rate = success_rate(self._feedback_history)
        symbol = "✓" if ok else "✗"
        logging.info(
            f"[Feedback] {symbol} | Session success rate: {rate:.1%} "
            f"({sum(self._feedback_history)}/{len(self._feedback_history)})"
        )

    def _build_metrics_entry(self, ok: bool) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.metrics_session_id,
            "model": self._current_model_key,
            "user_success": ok,
            **self._last_metrics,
        }

    def _persist_metrics(self, entry: dict) -> None:
        save_command_result(self.metrics_session_id, entry)

    # ── Carregamento de modelo ───────────────────────────────────────────────────

    def load_model(self, model_key: str, model_change: str="small") -> None:
        """Carrega o modelo ASR em background.
        Idempotente — não recarrega se o modelo já estiver em cache ou carregando.
        """
        with SpeechToText._model_load_lock:
            if model_key in SpeechToText._model_events:
                return
            event = threading.Event()
            SpeechToText._model_events[model_key] = event

        def _load_async():
            loading_start_time = time.time()
            try:
                backend, model_name = _parse_model_key(model_key)
                if model_change == "large": model_name = model_change
                loader = _BACKEND_LOADERS.get(backend)

                if loader is None:
                    raise ValueError(
                        f"Backend ASR desconhecido: '{backend}'. "
                        f"Disponíveis: {list(_BACKEND_LOADERS)}"
                    )

                logging.info(f"Carregando modelo ASR [{backend}]: {model_name}")
                SpeechToText._model_cache[model_key] = loader(model_name)
                loading_end_time = time.time()
                SpeechToText._model_load_times[model_key] = loading_end_time - loading_start_time

                logging.info(f"Modelo '{model_key}' pronto. Tempo de carregamento: {SpeechToText._model_load_times[model_key]:.2f} segundos.")

            except Exception:
                logging.exception(f"Falha ao carregar modelo '{model_key}'")
            finally:
                event.set()

        threading.Thread(target=_load_async, daemon=True).start()

    def _ensure_model(self) -> None:
        SpeechToText._model_events[self._current_model_key].wait()
        transcriber = SpeechToText._model_cache.get(self._current_model_key)
        if transcriber is None:
            raise RuntimeError(f"Modelo '{self._current_model_key}' não foi carregado corretamente.")
        self._transcriber = transcriber

    # ── API pública de escuta ────────────────────────────────────────────────────

    def listen_for_command(self) -> str | None:
        text = self._listen_and_transcribe()

        if not self._stop_requested and text:
            translation_tasks(text)

        return text

    def transcribe_continuously(self, text_callback=None) -> str:
        self.recognizer.pause_threshold = 3.0

        return self._listen_and_transcribe_background(text_callback=text_callback)

    def stop_listen(self) -> None:
        self._stop_requested = True

        if self.stop_listening:
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None
            logging.info("Listening stopped successfully.")
        else:
            logging.info("Command listening: waiting for natural timeout.")

        if hasattr(self, "_stop_event"):
            self._stop_event.set()

    # ── Escuta e transcrição ─────────────────────────────────────────────────────

    def _calibrate_microphone(self, source) -> None:
        self.recognizer.adjust_for_ambient_noise(source, duration=1)
        logging.info("Adjusted for ambient noise. Listening...")

    def _listen_and_transcribe(self, phrase_time_limit: int = 7) -> str | None:
        with sr.Microphone() as microphone:
            self._calibrate_microphone(microphone)

            try:
                audio = self.recognizer.listen(
                    microphone, timeout=4, phrase_time_limit=phrase_time_limit
                )
                logging.info(f"Listen end: {audio}")

                result = self._recognize_and_measure(audio)
                if result:
                    _, text = result
                    return text

            except sr.WaitTimeoutError:
                logging.error("Listening timeout while waiting for a phrase to start")

            except Exception as e:
                logging.error(f"Error: {e}")
                time.sleep(0.5)

        return None

    def _listen_and_transcribe_background(self, text_callback=None, silence_timeout: int = 20) -> str:
        self._collected_texts = []
        self._stop_event = threading.Event()
        self._last_audio_time = time.time()

        def _on_audio(recognizer, audio):
            self._last_audio_time = time.time()
            result = self._recognize_and_measure(audio)
            if result:
                metrics, text = result
                entry = self._build_metrics_entry(ok=False)
                save_transcription_result(self.metrics_session_id, entry)
                if text:
                    self._collected_texts.append(text)
                    save_text(f"{time.strftime('%H:%M:%S')} - {text}")
                    if text_callback:
                        text_callback(text)

        def _silence_watchdog():
            while not self._stop_event.is_set():
                if time.time() - self._last_audio_time > silence_timeout:
                    logging.info(f"Silence timeout ({silence_timeout}s) — ending transcription.")
                    self._stop_event.set()
                    break
                time.sleep(1)

        microphone = sr.Microphone()
        with microphone as source:
            self._calibrate_microphone(source)

        self.stop_listening = self.recognizer.listen_in_background(
            microphone, _on_audio, phrase_time_limit=4
        )
        threading.Thread(target=_silence_watchdog, daemon=True).start()

        self._stop_event.wait()

        if self.stop_listening:
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None

        return " ".join(self._collected_texts)

    # ── Reconhecimento e métricas ────────────────────────────────────────────────

    def _transcribe_audio(self, audio) -> tuple[str, list, float | None]:
        self._ensure_model()
        if isinstance(audio, (str, Path)):
            with sr.AudioFile(str(audio)) as source:
                audio_obj = self.recognizer.record(source)
        else:
            audio_obj = audio
        wav_bytes = audio_obj.get_wav_data(convert_rate=16000, convert_width=2)
        return self._transcriber(wav_bytes)

    def _recognize_and_measure(self, audio, reference: str | None = None) -> tuple[dict, str] | None:
        try:
            statup_end_time = time.time()
            statup_start_time = self._startup_start_time
            self._startup_start_time = None

            start_time = time.time()
            recognized_text, segments, audio_duration = self._transcribe_audio(audio)
            end_time = time.time()

            logging.info(f"Recognized: {recognized_text}")

            self._last_metrics = analyze_transcription(
                hypothesis=recognized_text,
                reference=reference,
                loading_model_time=SpeechToText._model_load_times.get(self._current_model_key),
                statup_start_time=statup_start_time,
                statup_end_time=statup_end_time,
                start_time=start_time,
                end_time=end_time,
                audio_duration_s=audio_duration,
                segments=segments,
            )
            self._last_transcription = recognized_text

            return self._last_metrics, recognized_text

        except sr.UnknownValueError:
            logging.error("Could not understand audio")

        except Exception as e:
            logging.error(f"Error during recognition: {e}")

        return None
