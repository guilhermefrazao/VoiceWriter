"""Runner headless de benchmark de ASR (sem GUI Flet, sem Supabase).

Roda um ou mais modelos faster-whisper sobre os datasets de benchmark
(commands + transcriptions) e grava métricas (WER, CER, BLEU, RTF, latência)
em CSV incremental + um resumo em Markdown.

Uso:
    uv run scripts/run_benchmark.py                       # sweep padrão
    uv run scripts/run_benchmark.py --models small large-v3
    uv run scripts/run_benchmark.py --datasets transcriptions

Projetado para rodar sem supervisão: escreve cada linha na hora (resultados
parciais sobrevivem a um crash) e isola falhas por amostra e por modelo.
"""
from __future__ import annotations

import argparse
import csv
import logging
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Permite rodar direto (uv run scripts/run_benchmark.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.utils import benchmark_manifest as bm
from voice.utils.asr_metrics import analyze_transcription

DEFAULT_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
RESULTS_ROOT = Path("benchmark_results")

CSV_FIELDS = [
    "model", "dataset", "id", "filename", "words_ref", "audio_duration_s",
    "cold_start", "inference_latency_ms", "rtf", "wer", "cer",
    "wer_normalized", "bleu_score", "avg_confidence", "hypothesis", "error",
]

log = logging.getLogger("run_benchmark")


def _load_model(model_name: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model_name, device="cuda", compute_type="float16")


def _transcribe(model, audio_path: Path):
    """Retorna (texto, segments, duração_s). Espelha o app."""
    segments, info = model.transcribe(
        str(audio_path), beam_size=5, language="pt", word_timestamps=True
    )
    segments = list(segments)
    text = "".join(s.text for s in segments).strip()
    return text, segments, getattr(info, "duration", None)


def run_sample(model, dataset, sample, cold_start: bool) -> dict:
    audio = bm.audio_path(dataset, sample)
    row = {f: None for f in CSV_FIELDS}
    row.update(
        model=None, dataset=dataset, id=sample.id, filename=sample.filename,
        words_ref=len(sample.reference.split()), cold_start=cold_start,
    )
    if not audio.exists():
        row["error"] = "audio ausente"
        return row
    try:
        start = time.time()
        text, segments, duration = _transcribe(model, audio)
        end = time.time()
        metrics = analyze_transcription(
            hypothesis=text,
            reference=sample.reference,
            start_time=start,
            end_time=end,
            audio_duration_s=duration,
            segments=segments,
            cold_start=cold_start,
        )
        row.update(
            audio_duration_s=round(duration, 2) if duration else None,
            inference_latency_ms=metrics["inference_latency_ms"],
            rtf=metrics["rtf"],
            wer=metrics["wer"],
            cer=metrics["cer"],
            wer_normalized=metrics["wer_normalized"],
            bleu_score=metrics["bleu_score"],
            avg_confidence=metrics["avg_confidence"],
            hypothesis=text,
        )
    except Exception as e:
        log.exception(f"Falha na amostra {dataset}/{sample.id}")
        row["error"] = f"{type(e).__name__}: {e}"
    return row


def build_summary(rows: list[dict]) -> str:
    def mean(subset, key):
        vals = [r[key] for r in subset if isinstance(r.get(key), (int, float))]
        return statistics.mean(vals) if vals else None

    def fmt(v, pct=False):
        if v is None:
            return "—"
        return f"{v:.1%}" if pct else f"{v:.3f}"

    header = (
        "| Modelo | Dataset | N | Erros | WER méd | WER mediana | CER méd | "
        "BLEU méd | RTF méd | Lat méd (ms) |\n"
        "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|"
    )
    lines = [header]
    for model in dict.fromkeys(r["model"] for r in rows):
        for dataset in ("commands", "transcriptions"):
            sub = [r for r in rows if r["model"] == model and r["dataset"] == dataset]
            if not sub:
                continue
            ok = [r for r in sub if r.get("error") is None]
            wers = [r["wer"] for r in ok if isinstance(r.get("wer"), (int, float))]
            lat = mean(ok, "inference_latency_ms")
            lines.append(
                f"| {model} | {dataset} | {len(sub)} | "
                f"{sum(1 for r in sub if r.get('error'))} | "
                f"{fmt(mean(ok,'wer'), True)} | "
                f"{fmt(statistics.median(wers) if wers else None, True)} | "
                f"{fmt(mean(ok,'cer'), True)} | "
                f"{fmt(mean(ok,'bleu_score'))} | "
                f"{fmt(mean(ok,'rtf'))} | "
                f"{f'{lat:.0f}' if lat is not None else '—'} |"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark headless de ASR (faster-whisper)")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                        help=f"tamanhos faster-whisper (padrão: {DEFAULT_MODELS})")
    parser.add_argument("--datasets", nargs="+", default=list(bm.VALID_DATASETS),
                        choices=bm.VALID_DATASETS)
    args = parser.parse_args()

    run_dir = RESULTS_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    csv_path = run_dir / "results.csv"
    summary_path = run_dir / "summary.md"

    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO, datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(run_dir / "run.log", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )

    manifests = {d: bm.load_manifest(d) for d in args.datasets}
    total = len(args.models) * sum(len(v) for v in manifests.values())
    log.info(f"Benchmark iniciado | modelos={args.models} datasets={args.datasets} "
             f"| {total} inferências | saída={run_dir}")

    all_rows: list[dict] = []
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        done = 0
        for model_name in args.models:
            t0 = time.time()
            log.info(f"=== Carregando modelo '{model_name}' ===")
            try:
                model = _load_model(model_name)
            except Exception as e:
                log.exception(f"Não foi possível carregar '{model_name}' — pulando")
                continue
            log.info(f"Modelo '{model_name}' carregado em {time.time()-t0:.1f}s")

            first = True
            for dataset in args.datasets:
                for sample in manifests[dataset]:
                    row = run_sample(model, dataset, sample, cold_start=first)
                    row["model"] = model_name
                    first = False
                    writer.writerow(row)
                    fh.flush()
                    all_rows.append(row)
                    done += 1
                    tag = "ERRO" if row.get("error") else f"WER={row['wer']:.1%}" if isinstance(row.get("wer"), float) else "ok"
                    log.info(f"[{done}/{total}] {model_name} {dataset}/{sample.id} {tag}")

            del model
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            # escreve resumo parcial a cada modelo concluído
            summary_path.write_text(
                f"# Benchmark ASR — {run_dir.name}\n\n"
                f"Modelos: {args.models} · Datasets: {args.datasets}\n\n"
                + build_summary(all_rows) + "\n",
                encoding="utf-8",
            )
            log.info(f"Resumo parcial atualizado após '{model_name}'.")

    log.info(f"✅ Benchmark concluído. CSV: {csv_path} | Resumo: {summary_path}")
    print("\n" + build_summary(all_rows))


if __name__ == "__main__":
    main()
