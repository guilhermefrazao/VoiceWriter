import csv
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR     = Path(__file__).parent.parent / "data"
_OFFLINE_QUEUE = _DATA_DIR / "offline_queue.json"
_CSV_PATH_COMMANDS      = _DATA_DIR / "metrics_commands.csv"
_CSV_PATH_STREAM      = _DATA_DIR / "metrics_streams.csv"

_CSV_COLUMNS = [
    "timestamp", "session_id", "model",
    "transcribed_text", "reference_text", "loading_model_time",
    "startup_latency_ms", "inference_latency_ms", "rtf", "avg_confidence",
    "wer", "cer", "wer_normalized",
    "wer_substitutions", "wer_deletions", "wer_insertions",
    "bleu_score", "user_success", "cold_start",
    "peak_memory_mb", "is_benchmark",
]

# Colunas aceitas por cada tabela no Supabase.
# Ajuste aqui sempre que adicionar/renomear colunas no banco.
_SB_TRANSCRIPTION = {
    "session_id", "model", "transcribed_text", "reference_text",
    "startup_latency_ms", "inference_latency_ms", "rtf", "avg_confidence",
    "wer", "cer", "wer_normalized", "wer_substitutions", "wer_deletions",
    "wer_insertions", "bleu_score", "user_success", "cold_start",
    "peak_memory_mb", "is_benchmark", "timestamp",
}
_SB_COMMAND = {
    "session_id", "model", "transcribed_text", "reference_text",
    "startup_latency_ms", "inference_latency_ms", "rtf", "avg_confidence",
    "wer", "cer", "wer_normalized", "wer_substitutions", "wer_deletions",
    "wer_insertions", "bleu_score", "user_success", "cold_start",
    "peak_memory_mb", "is_benchmark", "timestamp",
}
_SB_SESSION = {
    "id", "member_name", "model_name", "model_source",
    "scenario", "hardware_info", "started_at",
}


def _sb_filter(entry: dict, allowed: set) -> dict:
    return {k: v for k, v in entry.items() if k in allowed}


def _get_client():
    """Returns a configured Supabase client, or None if SUPABASE_URL/KEY are not set."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError:
        logging.warning("[Metrics] supabase-py não instalado — instale com: pip install supabase")
        return None


def _migrate_csv_columns_transcription() -> None:
    """Reescreve metrics.csv com o header atual quando _CSV_COLUMNS muda.

    Sem isso, um CSV existente mantém o header antigo (write_header só roda
    para arquivo novo), então colunas novas/reordenadas ficam desalinhadas
    ou o DictReader nunca encontra a chave nova.
    """
    with _CSV_PATH_STREAM.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with _CSV_PATH_STREAM.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _save_to_csv_transcription(entry: dict) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    if _CSV_PATH_STREAM.exists():
        with _CSV_PATH_STREAM.open(encoding="utf-8") as f:
            current_header = next(csv.reader(f), [])
        if current_header != _CSV_COLUMNS:
            _migrate_csv_columns_transcription()
    write_header = not _CSV_PATH_STREAM.exists()
    with _CSV_PATH_STREAM.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(entry)

def _migrate_csv_columns_commands() -> None:
    """Reescreve metrics.csv com o header atual quando _CSV_COLUMNS muda.

    Sem isso, um CSV existente mantém o header antigo (write_header só roda
    para arquivo novo), então colunas novas/reordenadas ficam desalinhadas
    ou o DictReader nunca encontra a chave nova.
    """
    with _CSV_PATH_STREAM.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with _CSV_PATH_STREAM.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _save_to_csv_commands(entry: dict) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    if _CSV_PATH_COMMANDS.exists():
        with _CSV_PATH_COMMANDS.open(encoding="utf-8") as f:
            current_header = next(csv.reader(f), [])
        if current_header != _CSV_COLUMNS:
            _migrate_csv_columns_commands()
    write_header = not _CSV_PATH_COMMANDS.exists()
    with _CSV_PATH_COMMANDS.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(entry)


def _queue_offline(entry: dict) -> None:
    _OFFLINE_QUEUE.parent.mkdir(exist_ok=True)
    records: list = []
    if _OFFLINE_QUEUE.exists():
        try:
            records = json.loads(_OFFLINE_QUEUE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            records = []
    records.append(entry)
    _OFFLINE_QUEUE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info(f"[Metrics] Salvo offline ({len(records)} na fila).")


def create_session(
    member_name: str,
    model_name: str,
    model_source: str,
    scenario: str,
    hardware_info: dict | None = None,
) -> str:
    """
    Cria uma sessão de avaliação e retorna o session_id (UUID).

    Args:
        member_name:   nome do membro da equipe (definido em MEMBER_NAME no .env)
        model_name:    ex: "distil-large-v3", "voxtral-mini-3b"
        model_source:  "huggingface" | "nemo" | "local"
        scenario:      "dictation" | "command"
        hardware_info: dict com info do hardware, ex: {"gpu": "RTX 3060", "cuda": "12.1"}
    """
    data = {
        "member_name": member_name,
        "model_name": model_name,
        "model_source": model_source,
        "scenario": scenario,
        "hardware_info": hardware_info or {},
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    client = _get_client()
    if client:
        try:
            result = client.table("sessions").insert(data).execute()
            session_id = result.data[0]["id"]
            logging.info(f"[Metrics] Sessão criada no Supabase: {session_id}")
            return session_id
        except Exception as e:
            logging.error(f"[Metrics] Falha ao criar sessão no Supabase: {e}")

    session_id = str(uuid.uuid4())
    _queue_offline({"_type": "session", "id": session_id, **data})
    logging.warning(f"[Metrics] Sessão salva offline: {session_id}")
    return session_id


def _log_metrics(entry: dict) -> None:
    print("[Metrics]", flush=True)
    for k, v in entry.items():
        print(f"  {k}: {v}", flush=True)


def save_transcription_result(session_id: str, data: dict) -> None:
    """
    Salva o resultado de uma transcrição.
    Tenta Supabase primeiro; em falha, enfileira no offline_queue.json.

    O dict `data` deve conter os campos retornados por analyze_transcription()
    mais quaisquer campos adicionais (ex: user_success, audio_duration_ms).
    """
    
    entry = {"session_id": session_id, **data}
    _save_to_csv_transcription(entry)
    #_log_metrics(entry)
    client = _get_client()
    if client:
        try:
            client.table("transcription_results").insert(_sb_filter(entry, _SB_TRANSCRIPTION)).execute()
            logging.info("[Metrics] Resultado de transcrição salvo no Supabase.")
            return
        except Exception as e:
            logging.error(f"[Metrics] Falha no Supabase, salvando offline: {e}")
    _queue_offline({"_type": "transcription_result", **entry})
    


def save_command_result(session_id: str, data: dict) -> None:
    """
    Salva o resultado de um comando de voz.
    Campos esperados em data: spoken_text, recognized_command, success, latency_ms.
    Campos opcionais: expected_command (para benchmark).
    """
    entry = {"session_id": session_id, **data}
    client = _get_client()
    _save_to_csv_commands(entry)
    #_log_metrics(entry)
    if client:
        try:
            client.table("command_results").insert(_sb_filter(entry, _SB_COMMAND)).execute()
            logging.info("[Metrics] Resultado de comando salvo no Supabase.")
            return
        except Exception as e:
            logging.error(f"[Metrics] Falha no Supabase, salvando offline: {e}")
    _queue_offline({"_type": "command_result", **entry})


def flush_offline_queue() -> int:
    """
    Lê o offline_queue.json e tenta reenviar todos os registros ao Supabase.
    Registros que falharem permanecem na fila.
    Retorna o número de registros sincronizados com sucesso.
    Chamado automaticamente no startup do app.
    """
    if not _OFFLINE_QUEUE.exists():
        return 0

    client = _get_client()
    if not client:
        logging.warning("[Metrics] Supabase não configurado — flush ignorado.")
        return 0

    try:
        records = json.loads(_OFFLINE_QUEUE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        logging.error("[Metrics] offline_queue.json corrompido — ignorando.")
        return 0

    if not records:
        return 0

    synced = 0
    failed = []

    for record in records:
        record_type = record.pop("_type", None)
        try:
            if record_type == "session":
                client.table("sessions").insert(_sb_filter(record, _SB_SESSION)).execute()
            elif record_type == "transcription_result":
                client.table("transcription_results").insert(_sb_filter(record, _SB_TRANSCRIPTION)).execute()
            elif record_type == "command_result":
                client.table("command_results").insert(_sb_filter(record, _SB_COMMAND)).execute()
            synced += 1
        except Exception as e:
            record["_type"] = record_type
            failed.append(record)
            logging.error(f"[Metrics] Falha ao sincronizar registro: {e}")

    if failed:
        _OFFLINE_QUEUE.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        _OFFLINE_QUEUE.unlink()

    logging.info(f"[Metrics] Sync: {synced} enviados, {len(failed)} na fila.")
    return synced
