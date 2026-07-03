"""Fonte de verdade dos datasets de benchmark de ASR.

Carrega, valida e salva os manifestos JSON em voice/benchmark_wav/.
Consumido tanto pelo gravador CLI quanto pelos pipelines de benchmark.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BENCHMARK_DIR = Path("voice/benchmark_wav")

VALID_DATASETS = ("commands", "transcriptions")


@dataclass
class BenchmarkSample:
    id: int
    filename: str
    reference: str
    recorded_by: str | None


def _check_dataset(dataset: str) -> None:
    if dataset not in VALID_DATASETS:
        raise ValueError(f"Dataset inválido: {dataset!r}. Use um de {VALID_DATASETS}.")


def manifest_path(dataset: str) -> Path:
    _check_dataset(dataset)
    return BENCHMARK_DIR / f"{dataset}.json"


def audio_dir(dataset: str) -> Path:
    _check_dataset(dataset)
    return BENCHMARK_DIR / dataset


def audio_path(dataset: str, sample: BenchmarkSample) -> Path:
    return audio_dir(dataset) / sample.filename


def load_manifest(dataset: str) -> list[BenchmarkSample]:
    path = manifest_path(dataset)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ValueError(f"Manifesto não encontrado: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Manifesto malformado em {path}: {e}") from e

    samples = [
        BenchmarkSample(
            id=item["id"],
            filename=item["filename"],
            reference=item["reference"],
            recorded_by=item.get("recorded_by"),
        )
        for item in raw
    ]

    seen: set[int] = set()
    for s in samples:
        if s.id in seen:
            raise ValueError(f"id duplicado no manifesto {path}: {s.id}")
        seen.add(s.id)

    return samples


def save_manifest(dataset: str, samples: list[BenchmarkSample]) -> None:
    path = manifest_path(dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "id": s.id,
            "filename": s.filename,
            "reference": s.reference,
            "recorded_by": s.recorded_by,
        }
        for s in samples
    ]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def pending_samples(samples: list[BenchmarkSample]) -> list[BenchmarkSample]:
    return [s for s in samples if s.recorded_by is None]


def mark_recorded(samples: list[BenchmarkSample], sample_id: int, member: str) -> None:
    for s in samples:
        if s.id == sample_id:
            s.recorded_by = member
            return
    raise ValueError(f"id não encontrado no manifesto: {sample_id}")
