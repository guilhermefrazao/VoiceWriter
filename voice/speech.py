import speech_recognition as sr
import logging
import time
import sys
import io
import pyaudio
import queue
import numpy as np
import threading
import math
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable

from dotenv import load_dotenv
load_dotenv()

from voice.interact_app import translation_tasks
from voice.utils.json_utils import save_text
from voice.utils.asr_metrics import analyze_transcription, success_rate
from voice.utils.metrics_storage import save_metrics_local, save_metrics_cloud
from main import ASR_MODEL_KEY


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


def _load_faster_whisper(model_name: str) -> _Transcriber:
    """
    CTranslate2 + CUDA float16.
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

def _load_canary(model_name: str) -> _Transcriber:
    """
    NVIDIA Canary via NeMo — encoder-decoder multilingual (en/de/fr/es).
    NeMo.transcribe() exige caminhos de arquivo; áudio é salvo em temp file.
    Requer: pip install 'nemo_toolkit[asr]'
    """
    import os, tempfile
    import soundfile as sf
    import nemo.collections.asr as nemo_asr

    model = nemo_asr.models.ASRModel.from_pretrained(model_name="nvidia/canary-1b-v2")
    model.eval()

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, 16000)
            tmp_path = f.name

        try:
            output = model.transcribe([tmp_path])
            result = output[0] if output else ""
            # NeMo pode retornar str ou Hypothesis (com atributo .text)
            text = result.text if hasattr(result, "text") else str(result)
        finally:
            os.unlink(tmp_path)

        return text.strip(), [], duration

    return _transcribe


def _load_parakeet(model_name: str) -> _Transcriber:
    """
    NVIDIA Parakeet via NeMo — modelo CTC/TDT compacto (inglês).
    Mesmo framework do Canary; usa temp file para compatibilidade com NeMo.
    Requer: pip install 'nemo_toolkit[asr]'
    """
    import os, tempfile
    import soundfile as sf
    from nemo.collections.asr.models import ASRModel

    model = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v3")
    model.eval()

    def _transcribe(wav_bytes: bytes) -> tuple[str, list, float | None]:
        audio = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000.0

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, 16000)
            tmp_path = f.name

        try:
            output = model.transcribe([tmp_path])
            result = output[0] if output else ""
            text = result.text if hasattr(result, "text") else str(result)
        finally:
            os.unlink(tmp_path)

        return text.strip(), [], duration

    return _transcribe


def _load_voxtral(model_name: str) -> _Transcriber:
    """
    Mistral Voxtral via transformers — LLM causal multimodal com entrada de áudio.
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
    "voxtral-mini": _load_voxtral
}


class SpeechToText():
    _model_cache: dict[str, _Transcriber] = {}
    _model_events: dict[str, threading.Event] = {}
    _model_load_lock = threading.Lock()


    def __init__(self):
        self.is_recording = False
        self.stop_listening = None

        self._current_model_key = ASR_MODEL_KEY
        self._feedback_history: list[bool] = []
        self._session_id: str = str(uuid.uuid4())
        self._last_metrics: dict = {}
        self._last_transcription: str | None = None
        self._transcriber: _Transcriber | None = None
        self.load_model(ASR_MODEL_KEY)


    def record_feedback(self, ok: bool) -> None:
        self._feedback_history.append(ok)
        rate = success_rate(self._feedback_history)
        logging.info(f"[Feedback] {'✓' if ok else '✗'} | Session success rate: {rate:.1%} ({sum(self._feedback_history)}/{len(self._feedback_history)})")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "model": self._current_model_key,
            "transcribed_text": self._last_transcription,
            "user_success": ok,
            **self._last_metrics,
        }

        save_metrics_local(entry)
        save_metrics_cloud(entry)


    def load_model(self, model_key: str):
        """
        Carrega o modelo ASR identificado por model_key em background.
        Dispatcher: analisa o prefixo do model_key e delega ao loader correto.
        Idempotente — não recarrega se o modelo já estiver em cache ou carregando.
        """
        with SpeechToText._model_load_lock:
            if model_key in SpeechToText._model_events:
                return
            event = threading.Event()
            SpeechToText._model_events[model_key] = event

        def _load_async():
            try:
                backend, model_name = _parse_model_key(model_key)
                loader = _BACKEND_LOADERS.get(backend)
            
                if loader is None:
                    raise ValueError(f"Backend ASR desconhecido: '{backend}'. "f"Disponíveis: {list(_BACKEND_LOADERS)}")
            
                logging.info(f"Carregando modelo ASR [{backend}]: {model_name}")
            
                SpeechToText._model_cache[model_key] = loader(model_name)
            
                logging.info(f"Modelo '{model_key}' pronto.")
            
            except Exception as e:
                logging.error(f"Falha ao carregar modelo '{model_key}': {e}")
            
            finally:
                event.set()

        threading.Thread(target=_load_async, daemon=True).start()


    def _ensure_model(self):
        SpeechToText._model_events[self._current_model_key].wait()
        transcriber = SpeechToText._model_cache.get(self._current_model_key)
        if transcriber is None:
            raise RuntimeError(f"Modelo '{self._current_model_key}' não foi carregado corretamente.")
        self._transcriber = transcriber


    def main_commands(self) -> str | None:
        self._current_model_key = ASR_MODEL_KEY
        self._stop_requested = False
        self.load_model(ASR_MODEL_KEY)

        text = self._listen_and_transcribe()

        if not self._stop_requested and text:
            translation_tasks(text)

        return text


    def main_transcription(self, text_callback=None) -> str:
        self._current_model_key = ASR_MODEL_KEY
        self.load_model(ASR_MODEL_KEY)

        self.recognizer.pause_threshold = 3.0

        text = self._listen_and_transcribe_background(text_callback=text_callback)

        return text


    def _listen_and_transcribe(self, phrase_time_limit=7, stream=False) -> tuple[str, str]:
         with sr.Microphone() as microphone:
            self.recognizer.adjust_for_ambient_noise(microphone, duration=1)

            logging.info("Adjusted for ambient noise. Linstening...")

            try:
                audio = self.recognizer.listen(microphone, timeout=4, phrase_time_limit=phrase_time_limit, stream=stream)

                logging.info(f"Listen end: {audio}")

                text_log, text = self._recognize_speech_turbo(audio)

                return text

            except sr.WaitTimeoutError:
                logging.error("Listenting timeout while waiting for a phrase to start")

            except Exception as e:
                logging.error(f"Error {e}")
                time.sleep(0.5)


    def _listen_and_transcribe_background(self, text_callback=None, silence_timeout: int = 20) -> str:
        self._collected_texts = []
        self._stop_event = threading.Event()
        self._last_audio_time = time.time()

        def _callback(recognizer, audio):
            self._last_audio_time = time.time()
            result = self._recognize_speech_turbo(audio)
            if result:
                text_log, text = result
                if text:
                    self._collected_texts.append(text)
                    save_text(text_log)
                    if text_callback:
                        text_callback(text)

        def _silence_watchdog():
            while not self._stop_event.is_set():
                if time.time() - self._last_audio_time > silence_timeout:
                    logging.info(f"Timeout por silêncio ({silence_timeout}s) — encerrando transcrição.")
                    self._stop_event.set()
                    break
                time.sleep(1)

        microphone = sr.Microphone()

        with microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        logging.info("Adjusted for ambient noise. Listening...")

        self.stop_listening = self.recognizer.listen_in_background(
            microphone, _callback, phrase_time_limit=4
        )

        threading.Thread(target=_silence_watchdog, daemon=True).start()

        self._stop_event.wait()

        if self.stop_listening:
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None

        full_text = " ".join(self._collected_texts)
        full_log = f"{time.strftime('%H:%M:%S')} - {full_text}"

        return full_text


    def stop_listen(self):
        self._stop_requested = True

        if self.stop_listening:
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None
            logging.info("Escuta interrompida com sucesso.")
        else:
            logging.info("Escuta de comandos: aguardando timeout natural.")

        if hasattr(self, "_stop_event"):
            self._stop_event.set()


    def _recognize_speech_turbo(self, audio, reference: str | None = None) -> tuple[str, str]:
        self._ensure_model()
        try:
            s_time = time.time()
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)

            texto_reconhecido, segments, audio_duration = self._transcriber(wav_data)

            logging.info(f"Recognizing speech: {texto_reconhecido}")
            end_time = time.time()

            self._last_metrics = analyze_transcription(
                hypothesis=texto_reconhecido,
                reference=reference,
                start_time=s_time,
                end_time=end_time,
                audio_duration_s=audio_duration,
                segments=segments,
            )
            self._last_transcription = texto_reconhecido

            text_log = f"{time.strftime('{%H:%M:%S}')} + - + {texto_reconhecido}"

            return text_log, texto_reconhecido

        except sr.UnknownValueError:
            logging.error("Could not understand")

        except Exception as e:
            logging.error(f"Error during recognition: {e}")
