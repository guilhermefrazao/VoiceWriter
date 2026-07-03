import logging
import sys

from voice.speech import SpeechToText


class TypeAtCursorMode:
    def __init__(self) -> None:
        self.speech = SpeechToText()
        self.running = False

    def _type_text(self, text: str) -> None:
        import pyperclip
        import pyautogui

        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")

    def run(self) -> None:
        self.running = True
        logging.info("Type-at-cursor mode started. Press Ctrl+C to stop.")

        try:
            while self.running:
                self.speech.transcribe_continuously(text_callback=self._type_text)
        except KeyboardInterrupt:
            logging.info("Type-at-cursor mode stopped.")
            self.running = False
