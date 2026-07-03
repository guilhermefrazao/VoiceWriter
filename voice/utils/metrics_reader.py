"""
Leitura das métricas de ASR no Supabase para análise/dashboard.

Contraparte de leitura do metrics_storage.py (que só escreve). Retorna
DataFrames pandas prontos para agregar por modelo em notebooks/analysis.ipynb.

A identidade do modelo vive em `sessions.model_name`, não na linha de
resultado — por isso load_transcriptions()/load_commands() fazem o join.

Uso:
    from voice.utils.metrics_reader import load_transcriptions, load_commands
    df_t = load_transcriptions()   # transcription_results + sessions
    df_c = load_commands()         # command_results + sessions
"""
import logging
import os

import pandas as pd

# Supabase (PostgREST) retorna no máximo ~1000 linhas por request; paginamos.
_PAGE = 1000

# Colunas de sessions trazidas para a linha de resultado no join.
_SESSION_COLS = [
    "model_name", "model_source", "member_name", "scenario",
    "hardware_info", "started_at",
]


def get_client():
    """Cliente Supabase configurado, ou None se SUPABASE_URL/KEY não estiverem no ambiente.

    Espelha metrics_storage._get_client(). Carregue o .env antes (load_dotenv()).
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logging.warning("[MetricsReader] SUPABASE_URL/SUPABASE_KEY não configurados.")
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except ImportError:
        logging.warning("[MetricsReader] supabase-py não instalado — pip install supabase")
        return None


def _fetch_all(client, table: str) -> list[dict]:
    """Lê todas as linhas de `table` paginando de _PAGE em _PAGE via .range()."""
    rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            client.table(table)
            .select("*")
            .range(offset, offset + _PAGE - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < _PAGE:
            break
        offset += _PAGE
    return rows


def load_frames(client=None) -> dict[str, pd.DataFrame]:
    """Retorna {'sessions', 'transcription_results', 'command_results'} como DataFrames.

    DataFrame vazio para tabelas sem linhas (ou se o cliente não estiver configurado).
    """
    client = client or get_client()
    tables = ["sessions", "transcription_results", "command_results"]
    if client is None:
        return {t: pd.DataFrame() for t in tables}
    return {t: pd.DataFrame(_fetch_all(client, t)) for t in tables}


def _join_sessions(results: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """Left-join de um DataFrame de resultados com sessions (session_id -> id).

    Robusto a schema: só puxa as colunas de sessions que existirem de fato.
    """
    if results.empty:
        return results
    if sessions.empty or "id" not in sessions.columns:
        # Sem sessions não há como identificar o modelo; devolve o que veio.
        return results
    cols = ["id"] + [c for c in _SESSION_COLS if c in sessions.columns]
    return results.merge(
        sessions[cols],
        how="left",
        left_on="session_id",
        right_on="id",
        suffixes=("", "_session"),
    )


def load_transcriptions(client=None) -> pd.DataFrame:
    """transcription_results juntado com sessions (traz model_name, scenario, etc.)."""
    frames = load_frames(client)
    return _join_sessions(frames["transcription_results"], frames["sessions"])


def load_commands(client=None) -> pd.DataFrame:
    """command_results juntado com sessions (traz model_name, scenario, etc.)."""
    frames = load_frames(client)
    return _join_sessions(frames["command_results"], frames["sessions"])
