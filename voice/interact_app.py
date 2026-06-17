import logging
import re
import subprocess
import winsound
from pathlib import Path

from AppOpener import open, close

_SOUNDS_DIR = Path(__file__).parent / "sounds"


def translation_tasks(text: str) -> None:
    if not text:
        return

    comando = text.lower().strip()

    padrao_busca_executar = r'\b(abra|abrir|abre|abro|execute|executar|inicie)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)'

    padrao_busca_fechar = r"\b(feche|fechar|fecha|fecho|encerre|encerrar|encerra|encerro|pare|parar)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)"

    padrao_desligar_computador = r"\b(desligar|desligue|desliga)"

    padrao_ligar_aura = r"\b(alexa|ligar aura|aura)"

    resultado_ligar_aura = re.search(padrao_ligar_aura, comando)

    resultado_executar = re.search(padrao_busca_executar, comando)

    resultado_fechar = re.search(padrao_busca_fechar, comando)

    resultado_desligar = re.search(padrao_desligar_computador, comando)

    if resultado_ligar_aura:
        logging.info("Aura ativada!")
        _play_sound("ligar_aura.wav")

    elif resultado_executar:
        nome_do_app = resultado_executar.group(3).strip()
        
        logging.info(f"Comando identificado! Tentando abrir: {nome_do_app}...")

        open_app(nome_do_app)
                
    elif resultado_fechar:
        nome_do_app = resultado_fechar.group(3).strip()
        
        logging.info(f"Comando identificado! Tentando fechar: {nome_do_app}...")

        close_app(nome_do_app)

    elif resultado_desligar:
        subprocess.run(["shutdown", "/s", "/t", "0"])
        
    else:
        logging.info("Nenhum comando reconhecido nesta frase.")



def open_app(recognized_text: str)-> None:
    logging.info(f"Opening: {recognized_text}")
   
    inp = recognized_text.lower()

    open(inp, match_closest=True, throw_error=True)


def close_app(recognized_text: str)-> None:
    logging.info(f"Closing: {recognized_text}")
   
    inp = recognized_text.lower()

    close(inp, match_closest=True)


def _play_sound(filename: str) -> None:
    path = str(_SOUNDS_DIR / filename)
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)

