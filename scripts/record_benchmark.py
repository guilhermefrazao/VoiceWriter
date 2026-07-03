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
import sys
from pathlib import Path

# Permite rodar diretamente (uv run scripts/record_benchmark.py): garante que
# a raiz do projeto esteja no sys.path para importar o pacote `voice`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    pause_threshold: float = 0.8,
    phrase_time_limit: int = 30,
) -> int:
    samples = bm.load_manifest(dataset)
    recorded = 0
    # Quanto silêncio encerra a captura: alto o bastante para tolerar pausas
    # naturais entre frases em textos longos.
    recognizer.pause_threshold = pause_threshold
    for sample in bm.pending_samples(samples):
        choice = prompt_fn(sample.reference)
        if choice == "q":
            break
        if choice == "s":
            continue
        with mic_factory() as source:
            print("… calibrando ruído ambiente")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print(f"🎤 Pode falar agora... (pare por {pause_threshold:g}s ao terminar)")
            audio = recognizer.listen(
                source, timeout=10, phrase_time_limit=phrase_time_limit
            )
            print("✔ Gravado.")
        save_audio_wav(audio, bm.audio_path(dataset, sample))
        bm.mark_recorded(samples, sample.id, member)
        bm.save_manifest(dataset, samples)
        recorded += 1
    return recorded


# Ajustes de captura por dataset: comandos são curtos; transcrições são
# parágrafos longos com pausas naturais entre frases.
DATASET_TUNING = {
    "commands": {"pause_threshold": 0.8, "phrase_time_limit": 30},
    "transcriptions": {"pause_threshold": 3.0, "phrase_time_limit": 180},
}


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
        **DATASET_TUNING[args.dataset],
    )
    print(f"\n✅ {recorded} amostra(s) gravada(s) em '{args.dataset}'.")


if __name__ == "__main__":
    main()
