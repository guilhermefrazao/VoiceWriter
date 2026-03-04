import speech_recognition as sr
import logging
import time
import sys
import re
import io

from voice.interact_app import open_app, close_app
from faster_whisper import WhisperModel



logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", 
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.INFO, 
                    encoding="utf-8", 
                    handlers=[logging.FileHandler("voice.log", encoding="utf-8"),
                              logging.StreamHandler(sys.stdout)])


class Speech_to_text():
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recording_time = 30
        self.output_file = "output.txt"
        self.recognizer.pause_threshold = 1.5
        self.model = WhisperModel("small", device="cuda", compute_type="float16")


    def _listen_and_translate(self, stream=False) -> tuple[str, str]:
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

            


    def main_commands(self):
        text_log, text = self._listen_and_translate()

        self._save_text(text_log)

        self.translation_tasks(text)

        logging.info("Finished recording! Transcription saved to: %s", self.output_file)


    def main_translation(self)-> str:
        self.recognizer.pause_threshold = 3.0

        text_log, text = self._listen_and_translate()

        self._save_text(text_log)

        logging.info("Finished recording! Transcription saved to: %s", self.output_file)

        return text


    def _recognize_speech_turbo(self, audio) -> tuple[str, str]:
        try:
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
                
            wav_stream = io.BytesIO(wav_data)
            
            segmentos, info = self.model.transcribe(wav_stream, beam_size=5, language="pt")          
            
            texto_reconhecido = "".join([segment.text for segment in segmentos]).strip()
                
            logging.info(f"Recognizing speech: {texto_reconhecido}")
            
            timestamp = time.strftime("{%H:%M:%S}")
        
            return f"{timestamp} + - + {texto_reconhecido}", texto_reconhecido
        
        except sr.UnknownValueError:
            logging.error("Could not understand")
        
        except Exception as e:
            logging.error(f"Error during recognition: {e}")


    def _save_text(self, text: str):
        if text:
            with open(self.output_file, 'a') as f:
                f.write(text + '\n')


    def translation_tasks(self, text: str) -> None:
        if not text:
            return
    
        comando = text.lower().strip()

        padrao_busca_executar = r'\b(abra|abrir|abre|abro|execute|executar|inicie)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)'

        padrao_busca_fechar = r"\b(feche|fechar|fecha|fecho|encerre|encerrar|encerra|encerro|pare|parar)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)"
    
        resultado_executar = re.search(padrao_busca_executar, comando)

        resultado_fechar = re.search(padrao_busca_fechar, comando)

        if resultado_executar:
            nome_do_app = resultado_executar.group(3).strip()
            
            logging.info(f"Comando identificado! Tentando abrir: {nome_do_app}...")

            open_app(nome_do_app)
                    
        elif resultado_fechar:
            nome_do_app = resultado_fechar.group(3).strip()
            
            logging.info(f"Comando identificado! Tentando fechar: {nome_do_app}...")

            close_app(nome_do_app)
            
        else:
            logging.info("Nenhum comando reconhecido nesta frase.")



if __name__ == "__main__":
    audio_trascription = Speech_to_text()
    audio_trascription.main()