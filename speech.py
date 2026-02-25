import speech_recognition as sr
import logging
import time
import sys

from interact_app import open_browser, open_app



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


    def main(self):
        logging.info("Start recording")
        with sr.Microphone() as microphone:
            self.recognizer.adjust_for_ambient_noise(microphone, duration=1)
            logging.info("Adjusted for ambient noise. Linstening")
            
            try:
                audio = self.recognizer.listen(microphone, timeout=20, phrase_time_limit=5)
                
                text_log, text = self.recognize_speech(audio)
                
                self.save_text(text_log)

                self.process_input(text)

            except sr.WaitTimeoutError:
                logging.error("Listenting timeout while waiting for a phrase to start")
            
            except Exception as e:
                logging.error(f"Error {e}")
                time.sleep(0.5)

        logging.info("Finished recording! Transcription saved to: %s", self.output_file)


    def recognize_speech(self, audio) -> tuple[str, str]:
        try:
            text = self.recognizer.recognize_whisper(audio, model="small", show_dict=True, language="portuguese")
            timestamp = time.strftime("{%H:%M:%S}")
            
            logging.info(f"Recognizing speech: {text}")
        
            return f"{timestamp} + - + {text["text"]}", text["text"]
        
        except sr.UnknownValueError:
            logging.error("Could not understand")
        
        except Exception as e:
            logging.error(f"Error during recognition: {e}")


    def save_text(self, text: str):
        if text:
            with open(self.output_file, 'a') as f:
                f.write(text + '\n')


    def process_input(self, text: str) -> None:
        if not text:
            return
    
        comando = text.lower()
        logging.info(f"Analisando o comando: {comando}")

        if "abrir" in comando or "abra" in comando:
            
            if "google" in comando or "navegador" in comando:
                logging.info("Ação: Abrindo o Google...")
                open_browser()
                
            elif "bloco de notas" in comando or "anotação" in comando:
                logging.info("Ação: Abrindo o Bloco de Notas...")
                open_app("notepad.exe")
                
            elif "calculadora" in comando:
                logging.info("Ação: Abrindo a Calculadora...")
                open_app("calc.exe")
                
            else:
                logging.warning("Entendi que é para abrir algo, mas não sei o quê.")
                
        elif "fechar" in comando or "encerrar" in comando:
            logging.info("Ação: Comando de fechar ainda não implementado.")
            
        else:
            logging.info("Nenhum comando reconhecido nesta frase.")



if __name__ == "__main__":
    audio_trascription = Speech_to_text()
    audio_trascription.main()