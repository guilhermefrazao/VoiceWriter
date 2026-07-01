"""
Sincroniza registros da fila offline (voice/data/offline_queue.json) com o Supabase.
Execute após reconectar à internet:

    python scripts/sync_offline.py

Requer SUPABASE_URL e SUPABASE_KEY configurados no .env ou como variáveis de ambiente.
"""

import sys
from pathlib import Path

# Garante que o root do projeto está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from voice.utils.metrics_storage import flush_offline_queue, _OFFLINE_QUEUE


def main() -> None:
    if not _OFFLINE_QUEUE.exists():
        print("Nenhum registro offline pendente.")
        return

    import json
    try:
        records = json.loads(_OFFLINE_QUEUE.read_text(encoding="utf-8"))
    except Exception:
        records = []

    if not records:
        print("Fila offline vazia.")
        return

    print(f"{len(records)} registro(s) pendente(s). Sincronizando com Supabase...")
    synced = flush_offline_queue()
    print(f"Sincronizado: {synced} registro(s).")

    if _OFFLINE_QUEUE.exists():
        remaining = json.loads(_OFFLINE_QUEUE.read_text(encoding="utf-8"))
        print(f"Ainda na fila (falhas): {len(remaining)} registro(s).")


if __name__ == "__main__":
    main()
