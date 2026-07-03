"""
Visualizador de métricas do VoiceWriter — lê voice/data/metrics.csv no terminal.

Uso:
    python -m voice.utils.metrics_viewer                  # resumo por modelo (padrão)
    python -m voice.utils.metrics_viewer --group session  # resumo por sessão
    python -m voice.utils.metrics_viewer --raw            # todas as linhas
    python -m voice.utils.metrics_viewer --raw --tail 20  # últimas 20 linhas
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


_CSV_PATH_COMMANDS = Path(__file__).parent.parent / "data" /  "metrics_commands.csv"
_CSV_PATH_STREAM = Path(__file__).parent.parent / "data" / "metrics_streams.csv"


def _load() -> list[dict]:
    if not _CSV_PATH_STREAM.exists():
        return []
    with _CSV_PATH_STREAM.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg_value(entries: list[dict], field: str) -> float | None:
    vals = [_to_float(e.get(field)) for e in entries]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _avg(entries: list[dict], field: str) -> str:
    val = _avg_value(entries, field)
    return f"{val:.3f}" if val is not None else "—"


def _success_rate(entries: list[dict]) -> str:
    total = len(entries)
    if not total:
        return "—"
    ok = sum(1 for e in entries if e.get("user_success") in ("True", "1", "true"))
    return f"{ok / total:.1%}"


def _print_table(headers: list[str], rows: list[list]) -> None:
    widths = [len(h) for h in headers]
    str_rows = [[str(cell) for cell in row] for row in rows]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    fmt = "| " + " | ".join("{:<" + str(w) + "}" for w in widths) + " |"

    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in str_rows:
        print(fmt.format(*row))
    print(sep)


def summary_by_model(rows: list[dict]) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row.get("model", "unknown")].append(row)

    headers = ["model", "registros", "load_model_ms (avg)", "startup_ms (avg)", "inference_ms (avg)", "rtf (avg)", "confidence (avg)", "wer (avg)", "sucesso"]
    table_rows = [
        [
            model,
            len(entries),
            _avg(entries, "loading_model_time"),
            _avg(entries, "startup_latency_ms"),
            _avg(entries, "inference_latency_ms"),
            _avg(entries, "rtf"),
            _avg(entries, "avg_confidence"),
            _avg(entries, "wer"),
            _success_rate(entries),
        ]
        for model, entries in sorted(
            groups.items(),
            key=lambda kv: _avg_value(kv[1], "wer") if _avg_value(kv[1], "wer") is not None else float("inf"),
        )
    ]

    print(f"\nResumo por modelo  —  {len(rows)} registros totais\n")
    _print_table(headers, table_rows)


def summary_by_session(rows: list[dict]) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row.get("session_id", "unknown")].append(row)

    headers = ["session_id", "modelo", "registros", "startup_ms (avg)", "inference_ms (avg)", "sucesso", "início"]
    table_rows = [
        [
            session_id[:8] + "…",
            entries[0].get("model", "—"),
            len(entries),
            _avg(entries, "startup_latency_ms"),
            _avg(entries, "inference_latency_ms"),
            _success_rate(entries),
            entries[0].get("timestamp", "—")[:19],
        ]
        for session_id, entries in sorted(
            groups.items(), key=lambda x: x[1][0].get("timestamp", "")
        )
    ]

    print(f"\nResumo por sessão  —  {len(rows)} registros totais\n")
    _print_table(headers, table_rows)


def show_raw(rows: list[dict], tail: int | None = None) -> None:
    if tail:
        rows = rows[-tail:]

    headers = ["timestamp", "modelo", "startup_ms", "inference_ms", "rtf", "confidence", "wer", "sucesso", "texto (prévia)"]

    def _preview(text: str) -> str:
        return (text[:45] + "…") if len(text) > 45 else text

    table_rows = [
        [
            row.get("timestamp", "")[:19],
            row.get("model", "—"),
            row.get("startup_latency_ms", "—"),
            row.get("inference_latency_ms", "—"),
            row.get("rtf", "—"),
            row.get("avg_confidence", "—"),
            row.get("wer", "—"),
            row.get("user_success", "—"),
            _preview(row.get("transcribed_text", "")),
        ]
        for row in rows
    ]

    label = f"últimas {tail}" if tail else "todos os registros"
    print(f"\nLinhas brutas  —  {label}\n")
    _print_table(headers, table_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualizador de métricas do VoiceWriter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--group",
        choices=["model", "session"],
        default="model",
        help="Agrupar por modelo ou sessão (padrão: model)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Mostrar linhas brutas sem agrupamento",
    )
    parser.add_argument(
        "--tail",
        type=int,
        metavar="N",
        help="Mostrar apenas as últimas N linhas (implica --raw)",
    )
    args = parser.parse_args()

    rows = _load()
    if not rows:
        print(f"Nenhum dado encontrado em {_CSV_PATH_STREAM}")
        return

    if args.raw or args.tail:
        show_raw(rows, tail=args.tail)
    elif args.group == "session":
        summary_by_session(rows)
    else:
        summary_by_model(rows)


if __name__ == "__main__":
    main()
