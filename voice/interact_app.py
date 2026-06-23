import configparser
import glob
import logging
import platform
import re
import subprocess
from difflib import get_close_matches
from pathlib import Path

_SYSTEM = platform.system()
_SOUNDS_DIR = Path(__file__).parent / "sounds"

# Cache populado na primeira chamada a _get_linux_apps()
# Chave: nome em lowercase (display name ou nome do executável)
# Valor: caminho/nome do executável
_LINUX_APP_CACHE: dict[str, str] | None = None


def _get_linux_apps() -> dict[str, str]:
    global _LINUX_APP_CACHE
    if _LINUX_APP_CACHE is not None:
        return _LINUX_APP_CACHE

    apps: dict[str, str] = {}
    desktop_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        str(Path.home() / ".local/share/applications"),
    ]

    for desktop_dir in desktop_dirs:
        for desktop_file in glob.glob(f"{desktop_dir}/*.desktop"):
            config = configparser.ConfigParser(interpolation=None)
            try:
                config.read(desktop_file, encoding="utf-8")
                if "Desktop Entry" not in config:
                    continue
                entry = config["Desktop Entry"]
                # Ignora entradas ocultas (ex: desinstaladores, entradas auxiliares)
                if entry.get("NoDisplay", "false").lower() == "true":
                    continue
                name = entry.get("Name", "").strip()
                exec_cmd = re.sub(r"%[uUfFdDnNickvm]", "", entry.get("Exec", "")).strip()
                executable = exec_cmd.split()[0] if exec_cmd else ""
                if not name or not executable:
                    continue
                apps[name.lower()] = executable
                # Também indexa pelo nome do binário (ex: "firefox" além de "mozilla firefox")
                apps[Path(executable).name.lower()] = executable
            except Exception:
                pass

    _LINUX_APP_CACHE = apps
    return apps


def _find_closest_linux_app(name: str) -> str | None:
    apps = _get_linux_apps()
    matches = get_close_matches(name, list(apps.keys()), n=1, cutoff=0.5)
    if not matches:
        return None
    logging.info(f"Closest match: '{matches[0]}' -> '{apps[matches[0]]}'")
    return apps[matches[0]]


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
        if _SYSTEM == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["shutdown", "-h", "now"])

    else:
        logging.info("Nenhum comando reconhecido nesta frase.")



def open_app(recognized_text: str) -> None:
    logging.info(f"Opening: {recognized_text}")
    inp = recognized_text.lower()

    if _SYSTEM == "Windows":
        from AppOpener import open as _open
        _open(inp, match_closest=True, throw_error=True)
    else:
        executable = _find_closest_linux_app(inp)
        if executable:
            try:
                subprocess.Popen(executable.split())
            except FileNotFoundError:
                logging.warning(f"Executável '{executable}' não encontrado.")
        else:
            logging.warning(f"Nenhum app correspondente a '{inp}' encontrado.")


def close_app(recognized_text: str) -> None:
    logging.info(f"Closing: {recognized_text}")
    inp = recognized_text.lower()

    if _SYSTEM == "Windows":
        from AppOpener import close as _close
        _close(inp, match_closest=True)
    else:
        executable = _find_closest_linux_app(inp)
        process_name = Path(executable).name if executable else inp
        subprocess.run(["pkill", "-x", process_name])


def _play_sound(filename: str) -> None:
    path = str(_SOUNDS_DIR / filename)

    if _SYSTEM == "Windows":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
        try:
            subprocess.Popen(["paplay", path])
        except FileNotFoundError:
            subprocess.Popen(["aplay", path])
