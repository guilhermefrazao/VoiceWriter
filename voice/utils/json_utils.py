import logging

def save_text(text: str):
    if text:
        with open("output.txt", 'a') as f:
            f.write(text + '\n')

    logging.info("Finished recording! Transcription saved to: %s", "output.txt")