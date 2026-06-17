import json
import logging
import os
from pathlib import Path

_LOCAL_FILE = Path(__file__).parent.parent / "data" / "feedback_metrics.json"


def save_metrics_local(entry: dict) -> None:
    _LOCAL_FILE.parent.mkdir(exist_ok=True)

    records: list = []
    if _LOCAL_FILE.exists():
        try:
            records = json.loads(_LOCAL_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            records = []

    records.append(entry)
    _LOCAL_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logging.info(f"[Metrics] Salvo localmente em {_LOCAL_FILE} ({len(records)} registros)")


def save_metrics_cloud(entry: dict) -> None:
    try:
        from pymongo import MongoClient

        uri = os.getenv("MONGODB_URI")
        if not uri:
            logging.warning("[Metrics] MONGODB_URI não configurado — salvamento na nuvem ignorado.")
            return

        db_name = os.getenv("MONGODB_DB", "voicewriter")

        client = MongoClient(uri, serverSelectionTimeoutMS=5_000)
        collection = client[db_name]["asr_feedback"]

        mongo_entry = {k: v for k, v in entry.items() if k != "_id"}
        collection.insert_one(mongo_entry)

        logging.info("[Metrics] Salvo no MongoDB Atlas.")
    except Exception as e:
        logging.error(f"[Metrics] Erro ao salvar no MongoDB: {e}")
