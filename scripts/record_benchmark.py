"""Gravador CLI guiado para os datasets de benchmark de ASR.

Uso:
    uv run python scripts/record_benchmark.py --dataset commands
    uv run python scripts/record_benchmark.py --dataset transcriptions

Para cada amostra pendente mostra a frase, grava pelo microfone e atualiza
o manifesto. NÃO importa Flet nem main.py.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import speech_recognition as sr
from dotenv import load_dotenv

from voice.utils import benchmark_manifest as bm


def save_audio_wav(audio_data: sr.AudioData, out_path: Path) -> None:
    wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(wav_bytes)


def _default_prompt(reference: str) -> str:
    print(f"\n📝 Frase: \"{reference}\"")
    return input("[Enter]=gravar  s=pular  q=sair > ").strip().lower()


def record_pending(
    dataset: str,
    member: str,
    recognizer,
    mic_factory,
    prompt_fn=_default_prompt,
) -> int:
    samples = bm.load_manifest(dataset)
    recorded = 0
    for sample in bm.pending_samples(samples):
        choice = prompt_fn(sample.reference)
        if choice == "q":
            break
        if choice == "s":
            continue
        with mic_factory() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
        save_audio_wav(audio, bm.audio_path(dataset, sample))
        bm.mark_recorded(samples, sample.id, member)
        bm.save_manifest(dataset, samples)
        recorded += 1
    return recorded


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Gravador de benchmark de ASR")
    parser.add_argument("--dataset", required=True, choices=bm.VALID_DATASETS)
    args = parser.parse_args()

    member = os.getenv("MEMBER_NAME", "anonimo")
    recognizer = sr.Recognizer()
    recorded = record_pending(
        args.dataset,
        member=member,
        recognizer=recognizer,
        mic_factory=sr.Microphone,
    )
    print(f"\n✅ {recorded} amostra(s) gravada(s) em '{args.dataset}'.")


if __name__ == "__main__":
    main()
