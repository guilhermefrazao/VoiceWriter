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

from voice.interact_app import translation_tasks
from voice.utils.json_utils import save_text
from faster_whisper import WhisperModel



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
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.silent_limit = 100
        self.silent_time = 0

        self.format = pyaudio.paInt16
        self.canais = 1
        self.taxa_amostragem = 16000
        self.tamanho_chunk = 16000

        self._load_model()

    
    def _load_model(self):
        if SpeechToText._cached_model is None:
            logging.info("Carregando Whisper Model.")
            SpeechToText._cached_model = WhisperModel("small", device="cuda", compute_type="float16")
        else:
            logging.info("Whisper Model já carregado.")
        self.model = SpeechToText._cached_model


    def main_commands(self):
        text_log, text = self._listen_and_transcribe()

        save_text(text_log)

        translation_tasks(text)


    def main_transcription(self, callback_function=None)-> str:
        self.recognizer.pause_threshold = 3.0
        
        #self.trancription_callback = callback_function

        #self._start_listen

        text_log, text = self._listen_and_transcribe()

        save_text(text_log)

        return text


    def _listen_and_transcribe(self, stream=False) -> tuple[str, str]:
         with sr.Microphone() as microphone:
            self.recognizer.adjust_for_ambient_noise(microphone, duration=1)

            logging.info("Adjusted for ambient noise. Linstening...")

            try:
                audio = self.recognizer.listen(microphone, timeout=10, phrase_time_limit=None, stream=stream)

                logging.info(f"Listen end: {audio}")

                text_log, text = self._recognize_speech_turbo(audio)

                return text_log, text

            except sr.WaitTimeoutError:
                logging.error("Listenting timeout while waiting for a phrase to start")
            
            except Exception as e:
                logging.error(f"Error {e}")
                time.sleep(0.5)


    def _recognize_speech_turbo(self, audio) -> tuple[str, str]:
        try:
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
                
            wav_stream = io.BytesIO(wav_data)
            
            segmentos, info = self.model.transcribe(wav_stream, beam_size=5, language="pt")          
            
            texto_reconhecido = "".join([segment.text for segment in segmentos]).strip()
                
            logging.info(f"Recognizing speech: {texto_reconhecido}")
        
            return f"{time.strftime("{%H:%M:%S}")} + - + {texto_reconhecido}", texto_reconhecido
        
        except sr.UnknownValueError:
            logging.error("Could not understand")
        
        except Exception as e:
            logging.error(f"Error during recognition: {e}")


    def _start_listen(self):
        self.is_recording = True
        self.audio_data_acumulado = b""
        
        self.p = pyaudio.PyAudio()
        
        self.stream = self.p.open(
            format=self.format,
            channels=self.canais,
            rate=self.taxa_amostragem,
            input=True,
            frames_per_buffer=self.tamanho_chunk,
            stream_callback=self._microfone_callback 
        )
        
        self.stream.start_stream()

        logging.info("Microfone aberto. Pode falar!")

        threading.Thread(target=self.real_time_transcription, daemon=True).start()


    def _microfone_callback(self, in_data, frame_count, time_info, status):
        if self.is_recording:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)


    def real_time_transcription(self):
        while self.is_recording:
            try:
                chunk = self.audio_queue.get(timeout=1.0)

                audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                
                volume = math.sqrt(np.mean(audio_array**2))
                
                logging.info(f"Volume: {volume}")

                if volume < self.silent_limit:
                    if self.silent_time == 0:
                        self.silent_time = time.time()
                    elif time.time() - self.silent_time > 1.5: 
                        logging.info("Silêncio detectado. Parando a gravação...")
                        self.stop_listen() 
                        break
                else:
                    self.silent_time = 0

                segmentos, info = self.model.transcribe(audio_array, language="pt", vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500), condition_on_previous_text=False)
                
                recognized_text = "".join([s.text for s in segmentos]).strip()
                
                logging.info(f"Ao vivo: {recognized_text}")

                if recognized_text:
                    self.trancription_callback(recognized_text)

            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Erro no processamento: {e}")


    def stop_listen(self):
        self.is_recording = False
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        logging.info("Microfone fechado.")







