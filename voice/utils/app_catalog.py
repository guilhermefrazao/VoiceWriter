"""
Catálogo de aplicativos instalados, usado pra resolver comandos de voz a apps
reais em vez de confiar cegamente no texto transcrito literal.

Linux: escaneia arquivos .desktop (padrão XDG). Windows: não implementado
aqui — a lib AppOpener já mantém seu próprio catálogo nesse SO (ver
voice/interact_app.py, que só usa este módulo quando ele retorna resultados).
"""

import logging
import os
import platform
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

_DESKTOP_DIRS = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    str(Path.home() / ".local/share/applications"),
    "/var/lib/snapd/desktop/applications",   # apps instalados via Snap
    "/var/lib/flatpak/exports/share/applications",  # Flatpak (sistema)
    str(Path.home() / ".local/share/flatpak/exports/share/applications"),  # Flatpak (usuário)
]

_FIELD_CODE_RE = re.compile(r"%[a-zA-Z%]")


@dataclass
class AppEntry:
    name: str
    exec_cmd: list[str]  # pronto pra subprocess.Popen(), sem shell=True
    binary: str          # nome do binário (sem path), útil pra pkill


def _parse_desktop_file(path: Path) -> AppEntry | None:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    parts = content.split("[Desktop Entry]", 1)
    if len(parts) < 2:
        return None
    body = parts[1].split("\n[", 1)[0]

    fields: dict[str, str] = {}
    for line in body.splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            fields.setdefault(key.strip(), value.strip())

    if fields.get("NoDisplay", "").lower() == "true":
        return None
    if fields.get("Hidden", "").lower() == "true":
        return None
    if fields.get("Type", "Application") != "Application":
        return None

    name = fields.get("Name")
    exec_line = fields.get("Exec")
    if not name or not exec_line:
        return None

    exec_line = _FIELD_CODE_RE.sub("", exec_line).strip()
    try:
        exec_cmd = shlex.split(exec_line)
    except ValueError:
        return None
    if not exec_cmd:
        return None

    binary = os.path.basename(exec_cmd[0])
    if binary in ("true", "false"):
        # Placeholders internos (comuns em pacotes Snap com múltiplos .desktop
        # por app — ex: um "daemon" auxiliar que nunca deveria ser lançado por
        # comando de voz). Ver .specs/roberto-tasks.md, caso "Chromium".
        return None

    return AppEntry(name=name, exec_cmd=exec_cmd, binary=binary)


_catalog_cache: dict[str, AppEntry] | None = None


def get_installed_apps() -> dict[str, AppEntry]:
    """
    {nome_de_exibição: AppEntry}. Cacheado em memória por processo — a lista
    de apps instalados não muda durante uma sessão do VoiceWriter. Vazio em
    qualquer plataforma != Linux.
    """
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    catalog: dict[str, AppEntry] = {}

    if platform.system() == "Linux":
        for dir_path in _DESKTOP_DIRS:
            d = Path(dir_path)
            if not d.is_dir():
                continue
            for desktop_file in sorted(d.glob("*.desktop")):
                entry = _parse_desktop_file(desktop_file)
                if entry and entry.name not in catalog:
                    catalog[entry.name] = entry

    logging.info(f"[AppCatalog] {len(catalog)} apps encontrados.")
    _catalog_cache = catalog
    return catalog
