import logging
import platform
import re
import subprocess

_SYSTEM = platform.system()

_ao_open = None
_ao_close = None
_HAS_APPOPENER = False

try:
    from AppOpener import open as _ao_open, close as _ao_close
    _HAS_APPOPENER = True
except (ImportError, ModuleNotFoundError):
    logging.warning("AppOpener unavailable (Windows-only). Using subprocess fallback for open/close.")

_OPEN_PATTERN     = re.compile(r'\b(abra|abrir|abre|abro|execute|executar|inicie)\s+(?:o\s+|a\s+|um\s+|uma\s+)?(.*)', re.IGNORECASE)
_CLOSE_PATTERN    = re.compile(r'\b(feche|fechar|fecha|fecho|encerre|encerrar|encerra|encerro|pare|parar)\s+(?:o\s+|a\s+|um\s+|uma\s+)?(.*)', re.IGNORECASE)
_SHUTDOWN_PATTERN = re.compile(r'\b(desligar|desligue|desliga)', re.IGNORECASE)


def translation_tasks(text: str) -> None:
    if not text:
        return

    normalized_text = text.lower().strip()

    open_match     = _OPEN_PATTERN.search(normalized_text)
    close_match    = _CLOSE_PATTERN.search(normalized_text)
    shutdown_match = _SHUTDOWN_PATTERN.search(normalized_text)

    if open_match:
        app_name = open_match.group(2).strip()
        logging.info(f"Command identified! Trying to open: {app_name}...")
        open_app(app_name)

    elif close_match:
        app_name = close_match.group(2).strip()
        logging.info(f"Command identified! Trying to close: {app_name}...")
        close_app(app_name)

    elif shutdown_match:
        if _SYSTEM == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["shutdown", "-h", "now"])

    else:
        logging.info("No command recognized in this phrase.")


def open_app(app_name: str) -> None:
    logging.info(f"Opening: {app_name}")
    normalized = app_name.lower()

    if _HAS_APPOPENER:
        _ao_open(normalized, match_closest=True, throw_error=True)
    else:
        subprocess.Popen(normalized, shell=True)


def close_app(app_name: str) -> None:
    logging.info(f"Closing: {app_name}")
    normalized = app_name.lower()

    if _HAS_APPOPENER:
        _ao_close(normalized, match_closest=True)
    else:
        subprocess.run(["pkill", "-fi", normalized])
