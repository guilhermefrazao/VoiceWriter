import speech_recognition as sr
import logging
import os
import time
import sys
import io
import numpy as np
import threading
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

def _parse_model_key(model_key: str) -> tuple[str, str]:
    """Separa 'backend:model_name' → ('backend', 'model_name')."""
    if ":" not in model_key:
        raise ValueError(f"model_key inválido: '{model_key}'. Use o formato 'backend:model_name'.")
    backend, model_name = model_key.split(":", 1)
    return backend.strip(), model_name.strip()


def display_model_name(model_key: str) -> str:
    """Nome curto para logs/UI: descarta o backend e o prefixo de empresa.
    'parakeet:nvidia/parakeet-tdt-0.6b-v3' -> 'parakeet-tdt-0.6b-v3'
    """
    _, model_name = _parse_model_key(model_key)
    return model_name.rsplit("/", 1)[-1]


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


def _make_nemo_transcriber(model, transcribe_kwargs: dict | None = None) -> _Transcriber:
    """Factory compartilhada pelos backends NeMo (Canary, Parakeet).
    NeMo.transcribe() exige caminhos de arquivo; áudio é salvo em temp file.
    transcribe_kwargs cobre parâmetros específicos do modelo (ex.: source_lang/
    target_lang, exigidos pelo Canary multilingual, mas não aceitos pelo Parakeet).
    """
    import os
    import tempfile
    import torch
    import soundfile as sf

    extra_kwargs = transcribe_kwargs or {}

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, 16000)
            tmp_path = f.name

        try:
            with torch.autocast("cuda", dtype=torch.float16):
                output = model.transcribe([tmp_path], num_workers=0, batch_size=1, **extra_kwargs)
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


def _disable_rnnt_cuda_graph_decoder(model, label: str) -> None:
    """Força o decoder greedy do RNNT/TDT a rodar em modo Python puro.
    NeMo captura o loop de decodificação greedy como um CUDA Graph para
    acelerar a inferência, fixando os endereços de tensor no shape de áudio
    da 1ª chamada. Uma 2ª chamada com duração diferente reaproveita memória
    já liberada → "CUDA error: an illegal memory access was encountered".
    Ver scripts/repro_parakeet_crash.py para o repro isolado do bug.
    """
    from omegaconf import open_dict

    try:
        decoding_cfg = model.cfg.decoding
        with open_dict(decoding_cfg):
            decoding_cfg.greedy.use_cuda_graph_decoder = False
        model.change_decoding_strategy(decoding_cfg)
        logging.info(f"[{label}] CUDA Graph decoder desativado (use_cuda_graph_decoder=False).")
    except Exception:
        logging.exception(f"[{label}] Falha ao desativar CUDA Graph decoder")


def _apply_gpu_optimizations() -> None:
    import torch
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True


def _load_canary(model_name: str) -> _Transcriber:
    """NVIDIA Canary via NeMo — encoder-decoder multilingual (en/de/fr/es).
    model_name esperado no formato "empresa/modelo", ex.: "nvidia/canary-1b-v2".
    Requer: pip install 'nemo_toolkit[asr]'
    """
    import nemo.collections.asr as nemo_asr

    _apply_gpu_optimizations()
    model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
    model = model.cuda()
    return _make_nemo_transcriber(model, {"source_lang": "pt", "target_lang": "pt"})


def _load_parakeet(model_name: str) -> _Transcriber:
    """NVIDIA Parakeet via NeMo — modelo CTC/TDT compacto (inglês).
    model_name esperado no formato "empresa/modelo", ex.: "nvidia/parakeet-tdt-0.6b-v3".
    Não aceita source_lang/target_lang (diferente do Canary).
    Requer: pip install 'nemo_toolkit[asr]'
    """
    from nemo.collections.asr.models import ASRModel

    _apply_gpu_optimizations()
    model = ASRModel.from_pretrained(model_name=model_name)
    model = model.cuda()
    _disable_rnnt_cuda_graph_decoder(model, "parakeet-v3")
    return _make_nemo_transcriber(model)


def _load_voxtral(model_name: str) -> _Transcriber:
    """Mistral Voxtral Realtime via transformers — ASR multilingual em streaming.
    model_name esperado no formato "empresa/modelo", ex.: "mistralai/Voxtral-Mini-4B-Realtime-2602".
    Classe própria (VoxtralRealtimeForConditionalGeneration) — AutoModelForCausalLM
    não reconhece a classe de processamento deste checkpoint.
    Requer: pip install 'transformers>=5.2.0' 'mistral-common[audio]'
    """
    import torch
    from transformers import AutoProcessor, VoxtralRealtimeForConditionalGeneration

    processor = AutoProcessor.from_pretrained(model_name)
    model = VoxtralRealtimeForConditionalGeneration.from_pretrained(
        model_name, device_map="auto", dtype=torch.float16
    )
    model.eval()

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0

        inputs = processor(audio, return_tensors="pt").to(model.device, dtype=model.dtype)

        with torch.no_grad():
            output_ids = model.generate(**inputs)

        text = processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()
        return text, [], duration

    return _transcribe


def _load_granite(model_name: str) -> _Transcriber:
    """IBM Granite Speech via transformers — LLM Granite com adapter de áudio (encoder + LoRA).
    model_name esperado no formato "empresa/modelo", ex.: "ibm-granite/granite-4.0-1b-speech".
    Requer: pip install transformers
    """
    import torch
    from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

    processor = AutoProcessor.from_pretrained(model_name)
    tokenizer = processor.tokenizer
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_name, device_map="cuda", dtype=torch.bfloat16
    )
    model.eval()

    chat = [
        {
            "role": "system",
            "content": "Knowledge Cutoff Date: April 2024.\nYou are Granite, developed by IBM. You are a helpful AI assistant.",
        },
        {"role": "user", "content": "<|audio|>can you transcribe the speech into a written format?"},
    ]
    prompt = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0
        wav = torch.from_numpy(audio).unsqueeze(0)

        inputs = processor(prompt, wav, device="cuda", return_tensors="pt").to("cuda")

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=512)

        input_len = inputs["input_ids"].shape[-1]
        text = tokenizer.decode(output_ids[0, input_len:], skip_special_tokens=True).strip()
        return text, [], duration

    return _transcribe


_BACKEND_LOADERS: dict[str, Callable[[str], _Transcriber]] = {
    "faster-whisper": _load_faster_whisper,
    "canary": _load_canary,
    "parakeet": _load_parakeet,
    "voxtral": _load_voxtral,
    "granite": _load_granite,
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
            model_name=display_model_name(self._current_model_key),
            model_source="huggingface",
            scenario="dictation",
        )
        flush_offline_queue()

    # Benchmark

    def run_benchmark_transcription(self, audio, reference):
        self.recognize_and_measure(audio, reference)
        entry = self._build_metrics_entry(ok=False)
        save_transcription_result(self.metrics_session_id, entry)

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
            "model": display_model_name(self._current_model_key),
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

    def transcribe_continuously(
        self,
        text_callback=None,
        phrase_time_limit: float = 2.0,
        silence_timeout: int = 7,
    ) -> str:
        self.recognizer.pause_threshold = 3.0

        return self._listen_and_transcribe_background(
            text_callback=text_callback,
            phrase_time_limit=phrase_time_limit,
            silence_timeout=silence_timeout,
        )

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

                result = self.recognize_and_measure(audio)
                if result:
                    _, text = result
                    return text

            except sr.WaitTimeoutError:
                logging.error("Listening timeout while waiting for a phrase to start")

            except Exception as e:
                logging.error(f"Error: {e}")
                time.sleep(0.5)

        return None

    def _listen_and_transcribe_background(
        self,
        text_callback=None,
        phrase_time_limit: float = 4,
        silence_timeout: int = 20,
    ) -> str:
        self._collected_texts = []
        self._stop_event = threading.Event()
        self._last_audio_time = time.time()

        def _on_audio(recognizer, audio):
            self._last_audio_time = time.time()
            result = self.recognize_and_measure(audio)
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
            microphone, _on_audio, phrase_time_limit=phrase_time_limit
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

    def recognize_and_measure(self, audio, reference: str | None = None) -> tuple[dict, str] | None:
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
