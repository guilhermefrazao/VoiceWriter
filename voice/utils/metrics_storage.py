import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_OFFLINE_QUEUE = Path(__file__).parent.parent / "data" / "offline_queue.json"


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


def save_transcription_result(session_id: str, data: dict) -> None:
    """
    Salva o resultado de uma transcrição.
    Tenta Supabase primeiro; em falha, enfileira no offline_queue.json.

    O dict `data` deve conter os campos retornados por analyze_transcription()
    mais quaisquer campos adicionais (ex: user_success, audio_duration_ms).
    """
    entry = {"session_id": session_id, **data}
    client = _get_client()
    if client:
        try:
            client.table("transcription_results").insert(entry).execute()
            logging.info("[Metrics] Resultado de transcrição salvo no Supabase.")
            return
        except Exception as e:
            logging.error(f"[Metrics] Falha no Supabase, salvando offline: {e}")
    _queue_offline({"_type": "transcription_result", **entry})


def save_command_result(session_id: str, data: dict) -> None:
    """
    Salva o resultado de uma transcrição em cenário de comando.

    Schema real da tabela `command_results` no Supabase (verificado em
    2026-07-03 via inspeção direta — diverge do documentado em
    scripts/setup_supabase.sql, que ficou desatualizado depois que o time
    evoluiu o schema na branch feat/models sem atualizar o arquivo):
    transcribed_text, reference_text, recognized_command, model,
    user_success, wer, cer, wer_normalized, wer_substitutions,
    wer_deletions, wer_insertions, bleu_score, rtf, avg_confidence,
    cold_start, peak_memory_mb, inference_latency_ms, startup_latency_ms,
    loading_model_time, is_benchmark, timestamp. Nenhum campo é obrigatório
    além do session_id (passado à parte). NÃO usar spoken_text/success/
    latency_ms/expected_command — não existem na tabela real e a inserção
    cai silenciosamente na fila offline.
    """
    entry = {"session_id": session_id, **data}
    client = _get_client()
    if client:
        try:
            client.table("command_results").insert(entry).execute()
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
                client.table("sessions").insert(record).execute()
            elif record_type == "transcription_result":
                client.table("transcription_results").insert(record).execute()
            elif record_type == "command_result":
                client.table("command_results").insert(record).execute()
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
