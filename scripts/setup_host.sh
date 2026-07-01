#!/usr/bin/env bash
# One-time host setup for VoiceWriter.
# Creates the libmpv.so.2 soname symlink that flet-desktop-0.81.x requires,
# then clears the stale flet desktop cache so flet doesn't try the broken binary.

set -euo pipefail

MPV_DIR="/usr/lib/x86_64-linux-gnu"
MPV_SO1="${MPV_DIR}/libmpv.so.1"
MPV_SO2="${MPV_DIR}/libmpv.so.2"
FLET_CACHE="${HOME}/.flet/client"

if [[ ! -f "${MPV_SO1}" ]]; then
    echo "ERROR: ${MPV_SO1} not found. Install libmpv1 first:"
    echo "  sudo apt-get install libmpv1"
    exit 1
fi

if [[ -e "${MPV_SO2}" ]]; then
    echo "OK: ${MPV_SO2} already exists, skipping symlink."
else
    sudo ln -s "${MPV_SO1}" "${MPV_SO2}"
    echo "Created: ${MPV_SO2} -> ${MPV_SO1}"
fi

sudo ldconfig
echo "ldconfig updated."

if [[ -d "${FLET_CACHE}/flet-desktop-0.81.0" ]]; then
    rm -rf "${FLET_CACHE}/flet-desktop-0.81.0"
    echo "Removed stale flet cache: flet-desktop-0.81.0"
else
    echo "No stale flet-desktop-0.81.0 cache found."
fi

echo "Host setup complete. You can now run: uv run python3 main.py"
