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

from dotenv import load_dotenv
load_dotenv()

from voice.interact_app import translation_tasks
from voice.utils.json_utils import save_text
from voice.utils.asr_metrics import analyze_transcription, success_rate
from voice.utils.metrics_storage import save_metrics_local, save_metrics_cloud
from faster_whisper import WhisperModel



logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", 
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO, 
                    encoding="utf-8", 
                    handlers=[logging.FileHandler("voice.log", encoding="utf-8"),
                              logging.StreamHandler(sys.stdout)])


class SpeechToText():
    _model_cache: dict = {}
    _model_events: dict = {}
    _model_load_lock = threading.Lock()


    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.5
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.stop_listening = None
        self.silent_limit = 100
        self.silent_time = 0

        self.format = pyaudio.paInt16
        self.canais = 1
        self.taxa_amostragem = 16000
        self.tamanho_chunk = 16000

        self._current_model_size = "small"
        self._feedback_history: list[bool] = []
        self._session_id: str = str(uuid.uuid4())
        self._last_metrics: dict = {}
        self._last_transcription: str | None = None
        self.load_model("small")


    def record_feedback(self, ok: bool) -> None:
        self._feedback_history.append(ok)
        rate = success_rate(self._feedback_history)
        logging.info(f"[Feedback] {'✓' if ok else '✗'} | Session success rate: {rate:.1%} ({sum(self._feedback_history)}/{len(self._feedback_history)})")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "model": self._current_model_size,
            "transcribed_text": self._last_transcription,
            "user_success": ok,
            **self._last_metrics,
        }

        save_metrics_local(entry)
        save_metrics_cloud(entry)


    def load_model(self, model_size: str):
        with SpeechToText._model_load_lock:
            if model_size in SpeechToText._model_events:
                return
            event = threading.Event()
            SpeechToText._model_events[model_size] = event

        def _worker():
            logging.info(f"Carregando Whisper Model: {model_size}.")
            SpeechToText._model_cache[model_size] = WhisperModel(model_size, device="cuda", compute_type="float16")
            logging.info(f"Whisper Model '{model_size}' pronto.")
            event.set()

        threading.Thread(target=_worker, daemon=True).start()


    def _ensure_model(self):
        SpeechToText._model_events[self._current_model_size].wait()
        self.model = SpeechToText._model_cache[self._current_model_size]


    def main_commands(self) -> str | None:
        self._current_model_size = "small"
        self._stop_requested = False
        self.load_model("small")

        text = self._listen_and_transcribe()

        if not self._stop_requested and text:
            translation_tasks(text)

        return text 


    def main_transcription(self, text_callback=None) -> str:
        self._current_model_size = "large-v2"
        self.load_model("large-v2")

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
            wav_stream = io.BytesIO(wav_data)

            segmentos, info = self.model.transcribe(wav_stream, beam_size=5, language="pt", word_timestamps=True)
            segmentos = list(segmentos)

            texto_reconhecido = "".join([segment.text for segment in segmentos]).strip()

            logging.info(f"Recognizing speech: {texto_reconhecido}")
            end_time = time.time()

            self._last_metrics = analyze_transcription(
                hypothesis=texto_reconhecido,
                reference=reference,
                start_time=s_time,
                end_time=end_time,
                audio_duration_s=info.duration if info else None,
                segments=segmentos,
            )
            self._last_transcription = texto_reconhecido

            text_log = f"{time.strftime('{%H:%M:%S}')} + - + {texto_reconhecido}"

            return text_log, texto_reconhecido

        except sr.UnknownValueError:
            logging.error("Could not understand")

        except Exception as e:
            logging.error(f"Error during recognition: {e}")