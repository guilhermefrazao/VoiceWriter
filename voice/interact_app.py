import logging
import platform
import re
import shlex
import subprocess

from voice.utils.app_catalog import get_installed_apps
from voice.utils.phonetic_match import best_match as best_match_heuristic
from voice.utils.phonetic_match_g2p import best_match as best_match_g2p

_ao_open = None
_ao_close = None
_HAS_APPOPENER = False

try:
    from AppOpener import open as _ao_open, close as _ao_close
    _HAS_APPOPENER = True
except (ImportError, ModuleNotFoundError):
    logging.warning("AppOpener unavailable (Windows-only). Using subprocess fallback for open/close.")


# Hoisted to module level (em vez de locais em translation_tasks) para serem
# reutilizados por scripts de benchmark sem duplicar a regex. Ver
# .specs/research/benchmark_real_commands.py.
#
# Conjugações abaixo foram ampliadas a partir de falhas reais observadas em
# .specs/research-command-phonetics.md §5.2 (33% das transcrições reais não
# batiam com nenhum verbo). Deliberadamente NÃO inclui "para" sozinho como
# forma de "parar": é também a preposição mais comum do português ("isso é
# para você"), e adicioná-la faria qualquer frase com "para o/a" virar um
# comando de fechar — falso positivo generalizado. "e para o Blender"
# continua sem casar; falso negativo pontual é preferível a esse risco.
PADRAO_BUSCA_EXECUTAR = (
    r'\b(abra|abrir|abre|abro|abri|abrei|abriu|abram|'
    r'execute|executar|executa|executei|executou|'
    r'inici\w*)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)'
)

PADRAO_BUSCA_FECHAR = (
    r"\b(feche|fechar|fecha|fecho|fechei|fechou|"
    r"encerre|encerrar|encerra|encerro|encerrei|encerrou|"
    r"pare|parar|parou)\s+(o\s+|a\s+|um\s+|uma\s+)?(.*)"
)

PADRAO_DESLIGAR_COMPUTADOR = r"\b(desligar|desligue|desliga)"


def translation_tasks(text: str) -> None:
    if not text:
        return

    comando = text.lower().strip()

    resultado_executar = re.search(PADRAO_BUSCA_EXECUTAR, comando)

    resultado_fechar = re.search(PADRAO_BUSCA_FECHAR, comando)

    resultado_desligar = re.search(PADRAO_DESLIGAR_COMPUTADOR, comando)

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


def _resolve_via_catalog(recognized_text: str) -> tuple:
    """
    Tenta casar recognized_text contra o catálogo de apps instalados,
    combinando duas fases (ver .specs/research-command-phonetics.md §5.4):
    Fase 2 (heurística — esqueleto consonantal) e Fase 3 (G2P real via
    g2p_en + epitran + panphon). As duas sempre rodam (custo medido:
    ~8ms no pior caso com catálogo de 117 apps, desprezível frente à
    latência de transcrição) e a decisão segue por votação:
      - só uma encontra algo -> usa essa.
      - as duas encontram e CONCORDAM -> usa (reforça confiança).
      - as duas encontram e DISCORDAM (apps diferentes) -> trata como
        inseguro, não resolve nada. Prefere falso negativo a escolher
        arbitrariamente entre dois palpites conflitantes — mesmo
        princípio já usado nos limiares de cada fase individualmente
        (falso positivo é pior que falso negativo num comando de voz).

    Retorna (AppEntry, descrição_str) ou (None, descrição_str).
    """
    catalog = get_installed_apps()
    if not catalog:
        return None, None

    r2 = best_match_heuristic(recognized_text, catalog)
    r3 = best_match_g2p(recognized_text, catalog)

    if r2.name and r3.name:
        if r2.name == r3.name:
            resolved_name = r2.name
            desc = f"Fase2+Fase3 concordam: {r2.name!r} (score={r2.score:.2f}, dist={r3.distance:.2f})"
        else:
            resolved_name = None
            desc = f"Fase2/Fase3 discordam: {r2.name!r} vs {r3.name!r} — descartado por segurança"
    elif r2.name:
        resolved_name = r2.name
        desc = f"Fase2: {r2.name!r} (score={r2.score:.2f})"
    elif r3.name:
        resolved_name = r3.name
        desc = f"Fase3 (fallback): {r3.name!r} (dist={r3.distance:.2f})"
    else:
        resolved_name = None
        desc = f"nenhuma fase encontrou (melhor Fase2 score={r2.score:.2f}, melhor Fase3 dist={r3.distance:.2f})"

    if resolved_name:
        return catalog[resolved_name], desc
    return None, desc


def open_app(recognized_text: str) -> None:
    entry, desc = _resolve_via_catalog(recognized_text)

    if entry:
        logging.info(f"Opening (matched): '{recognized_text}' -> '{entry.name}' [{desc}]")
        try:
            subprocess.Popen(entry.exec_cmd)
            return
        except OSError as e:
            logging.error(f"Falha ao executar '{entry.exec_cmd}': {e}")
    elif desc:
        logging.info(f"Nenhum app conhecido casou com '{recognized_text}' [{desc}] — usando fallback literal.")

    logging.info(f"Opening (fallback literal): {recognized_text}")
    inp = recognized_text.lower()

    try:
        if _HAS_APPOPENER:
            _ao_open(inp, match_closest=True, throw_error=True)
        else:
            subprocess.Popen(shlex.split(inp))
    except (OSError, ValueError) as e:
        logging.error(f"Falha ao abrir '{inp}': {e}")


def close_app(recognized_text: str) -> None:
    entry, desc = _resolve_via_catalog(recognized_text)

    if entry:
        logging.info(f"Closing (matched): '{recognized_text}' -> '{entry.name}' [{desc}]")
        subprocess.run(["pkill", "-fi", entry.binary])
        return
    elif desc:
        logging.info(f"Nenhum app conhecido casou com '{recognized_text}' [{desc}] — usando fallback literal.")

    logging.info(f"Closing (fallback literal): {recognized_text}")
    inp = recognized_text.lower()

    if _HAS_APPOPENER:
        _ao_close(inp, match_closest=True)
    else:
        subprocess.run(["pkill", "-fi", inp])
