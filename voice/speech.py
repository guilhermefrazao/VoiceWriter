import speech_recognition as sr
import logging
import time
import sys
import io
import threading

from dotenv import load_dotenv
load_dotenv()

from voice.interact_app import translation_tasks
from voice.utils.json_utils import save_text


logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO,
                    encoding="utf-8",
                    handlers=[logging.FileHandler("voice.log", encoding="utf-8"),
                              logging.StreamHandler(sys.stdout)])


class SpeechToText():
    _cached_model = None

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.5
        self.stop_listening = None


    def _load_model(self, model_size="small"):
        if SpeechToText._cached_model is None:
            from faster_whisper import WhisperModel
            logging.info("Carregando Whisper Model.")
            SpeechToText._cached_model = WhisperModel(model_size, device="cuda", compute_type="float16")
        else:
            logging.info("Whisper Model já carregado.")
        self.model = SpeechToText._cached_model


    def main_commands(self):
        self._load_model(model_size="small")
        text_log, text = self._listen_and_transcribe()
        translation_tasks(text)


    def main_transcription(self, text_callback=None) -> str:
        self._load_model(model_size="turbo")
        self.recognizer.pause_threshold = 3.0
        text_log, text = self._listen_and_transcribe_background(text_callback=text_callback)
        return text


    def _listen_and_transcribe(self, stream=False) -> tuple[str, str]:
        with sr.Microphone() as microphone:
            self.recognizer.adjust_for_ambient_noise(microphone, duration=1)
            logging.info("Adjusted for ambient noise. Listening...")

            try:
                audio = self.recognizer.listen(microphone, timeout=5, phrase_time_limit=10, stream=stream)
                logging.info(f"Listen end: {audio}")
                text_log, text = self._recognize_speech_turbo(audio)
                return text_log, text

            except sr.WaitTimeoutError:
                logging.error("Listening timeout while waiting for a phrase to start")

            except Exception as e:
                logging.error(f"Error {e}")
                time.sleep(0.5)


    def _listen_and_transcribe_background(self, text_callback=None) -> tuple[str, str]:
        self._collected_texts = []
        self._stop_event = threading.Event()

        def _callback(recognizer, audio):
            result = self._recognize_speech_turbo(audio)
            if result:
                text_log, text = result
                if text:
                    self._collected_texts.append(text)
                    save_text(text_log)
                    if text_callback:
                        text_callback(text)

        microphone = sr.Microphone()

        with microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        logging.info("Adjusted for ambient noise. Listening...")

        self.stop_listening = self.recognizer.listen_in_background(
            microphone, _callback, phrase_time_limit=5
        )

        self._stop_event.wait()

        full_text = " ".join(self._collected_texts)
        full_log = f"{time.strftime('%H:%M:%S')} - {full_text}"
        return full_log, full_text


    def stop_listen(self):
        if self.stop_listening:
            self.stop_listening(wait_for_stop=False)
            self.stop_listening = None
            logging.info("Escuta interrompida com sucesso.")
        else:
            logging.warning("Nenhuma escuta ativa para interromper.")

        if hasattr(self, "_stop_event"):
            self._stop_event.set()


    def _recognize_speech_turbo(self, audio) -> tuple[str, str]:
        try:
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
            wav_stream = io.BytesIO(wav_data)

            segmentos, info = self.model.transcribe(wav_stream, beam_size=5, language="pt")

            texto_reconhecido = "".join([segment.text for segment in segmentos]).strip()
            logging.info(f"Recognizing speech: {texto_reconhecido}")

            return f"{time.strftime('%H:%M:%S')} - {texto_reconhecido}", texto_reconhecido

        except sr.UnknownValueError:
            logging.error("Could not understand")

        except Exception as e:
            logging.error(f"Error during recognition: {e}")
