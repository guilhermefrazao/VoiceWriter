"""Repro standalone do crash "illegal memory access" no Parakeet-TDT.

Roda FORA do app (sem Flet, sem asyncio, sem asyncio.to_thread) e faz as duas
transcrições na MESMA thread. Isola se o bug é interno ao NeMo/CUDA Graphs do
decoder do Parakeet ou se depende do hand-off de thread do asyncio.to_thread
usado em frontend/widgets/mic.py e frontend/editor_menu.py.

Uso (dentro do container, com GPU disponível):
    python scripts/repro_parakeet_crash.py                    # durações diferentes (3s, 6s)
    python scripts/repro_parakeet_crash.py --same-duration    # controle: mesma duração (3s, 3s)

Rode CUDA_LAUNCH_BLOCKING=1 python scripts/repro_parakeet_crash.py para stacktrace síncrono.
"""

import argparse
import logging
import os
import tempfile
import threading

import numpy as np
import soundfile as sf
import torch

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def _log_decoding_diagnostics(model, label: str) -> None:
    try:
        logging.info(f"[{label}] decoding cfg: {getattr(model.cfg, 'decoding', None)}")
    except Exception:
        logging.exception(f"[{label}] Falha ao ler model.cfg.decoding")

    decoding_obj = getattr(model, "decoding", None)
    inner = getattr(decoding_obj, "decoding", None) if decoding_obj is not None else None
    for obj, obj_name in ((decoding_obj, "decoding"), (inner, "decoding.decoding")):
        if obj is None:
            continue
        graph_attrs = [a for a in dir(obj) if "graph" in a.lower() and not a.startswith("__")]
        logging.info(f"[{label}] {obj_name} class={type(obj).__name__} atributos-cuda-graph={graph_attrs}")
        for attr in graph_attrs:
            try:
                logging.info(f"[{label}] {obj_name}.{attr} = {getattr(obj, attr)}")
            except Exception:
                logging.info(f"[{label}] {obj_name}.{attr} = <erro ao ler>")


def _make_audio(duration_s: float, sample_rate: int = 16000) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sample_rate), endpoint=False)
    return (0.1 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)


def _save_wav(audio: np.ndarray, sample_rate: int = 16000) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(f.name, audio, sample_rate)
    return f.name


def _transcribe(model, wav_path: str, label: str) -> None:
    logging.info(f"--- Transcrição {label} | thread={threading.current_thread().name} ---")
    with torch.autocast("cuda", dtype=torch.float16):
        output = model.transcribe([wav_path], num_workers=0, batch_size=1)
    result = output[0] if output else ""
    text = (result.text if hasattr(result, "text") else str(result)).strip()
    logging.info(f"--- Resultado {label}: '{text}' ---")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--same-duration",
        action="store_true",
        help="Usa dois áudios de MESMA duração (controle). Default: durações diferentes (3s, 6s).",
    )
    args = parser.parse_args()

    from nemo.collections.asr.models import ASRModel

    logging.info(f"Thread principal: {threading.current_thread().name}")
    logging.info("Carregando nvidia/parakeet-tdt-0.6b-v3...")
    model = ASRModel.from_pretrained(model_name="nvidia/parakeet-tdt-0.6b-v3")
    model = model.cuda()
    _log_decoding_diagnostics(model, "parakeet-v3")
    logging.info("Modelo carregado.")

    dur_a = 3.0
    dur_b = 3.0 if args.same_duration else 6.0

    wav_a = _save_wav(_make_audio(dur_a))
    wav_b = _save_wav(_make_audio(dur_b))

    try:
        _transcribe(model, wav_a, f"1 (audio {dur_a}s)")
        _transcribe(model, wav_b, f"2 (audio {dur_b}s)")
        logging.info("OK — nenhum crash nas duas chamadas sequenciais na mesma thread.")
    finally:
        os.unlink(wav_a)
        os.unlink(wav_b)


if __name__ == "__main__":
    main()
