import logging
import platform
import re
import subprocess

_ao_open = None
_ao_close = None
_HAS_APPOPENER = False

try:
    from AppOpener import open as _ao_open, close as _ao_close
    _HAS_APPOPENER = True
except (ImportError, ModuleNotFoundError):
    logging.warning("AppOpener unavailable (Windows-only). Using subprocess fallback for open/close.")


def translation_tasks(text: str) -> None:
    if not text:
        return

    comando = text.lower().strip()

    padrao_busca_executar = r'\b(abra|abrir|abre|abro|execute|executar|inicie)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)'

    padrao_busca_fechar = r"\b(feche|fechar|fecha|fecho|encerre|encerrar|encerra|encerro|pare|parar)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)"

    padrao_desligar_computador = r"\b(desligar|desligue|desliga)"

    resultado_executar = re.search(padrao_busca_executar, comando)

    resultado_fechar = re.search(padrao_busca_fechar, comando)

    resultado_desligar = re.search(padrao_desligar_computador, comando)

    if resultado_executar:
        nome_do_app = resultado_executar.group(3).strip()
        
        logging.info(f"Comando identificado! Tentando abrir: {nome_do_app}...")

        open_app(nome_do_app)
                
    elif resultado_fechar:
        nome_do_app = resultado_fechar.group(3).strip()
        
        logging.info(f"Comando identificado! Tentando fechar: {nome_do_app}...")

        close_app(nome_do_app)

    elif resultado_desligar:
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["shutdown", "-h", "now"])
        
    else:
        logging.info("Nenhum comando reconhecido nesta frase.")



def open_app(recognized_text: str) -> None:
    logging.info(f"Opening: {recognized_text}")
    inp = recognized_text.lower()

    if _HAS_APPOPENER:
        _ao_open(inp, match_closest=True, throw_error=True)
    else:
        subprocess.Popen(inp, shell=True)


def close_app(recognized_text: str) -> None:
    logging.info(f"Closing: {recognized_text}")
    inp = recognized_text.lower()

    if _HAS_APPOPENER:
        _ao_close(inp, match_closest=True)
    else:
        subprocess.run(["pkill", "-fi", inp])

