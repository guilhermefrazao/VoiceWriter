"""Testa detecção de wakeword ao vivo pelo microfone usando um modelo
pré-treinado do openWakeWord (ex.: "hey jarvis"), sem precisar rodar o
pipeline de treino customizado (scripts/train_wakeword.py).

Uso:
    pip install openwakeword
    python scripts/test_wakeword_mic.py --model hey_jarvis

Fale a wakeword perto do microfone e observe os scores no terminal.
Ctrl-C para encerrar.
"""
import argparse
import logging

import numpy as np
import pyaudio

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms @ 16kHz


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default="hey_jarvis",
        help="Nome de um modelo pré-treinado do openWakeWord (baixado automaticamente) "
             "ou caminho para um .onnx/.tflite próprio.",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    from openwakeword.model import Model
    from openwakeword.utils import download_models

    is_builtin_name = "/" not in args.model and "\\" not in args.model and not args.model.endswith((".onnx", ".tflite"))
    if is_builtin_name:
        download_models([args.model])

    # tflite_runtime nesta venv não é compatível com numpy 2.x (usado pelo
    # pipeline de treino); onnx evita o conflito e é o backend que o listener
    # de runtime (ver docs/superpowers/plans/2026-07-02-wakeword-runtime-integration.md) também usa.
    model = Model(wakeword_models=[args.model], inference_framework="onnx")
    model_key = next(iter(model.models.keys()))
    logger.info("Modelo carregado: %s (limiar=%.2f)", model_key, args.threshold)

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SAMPLES,
    )
    logger.info("Escutando... fale a wakeword (Ctrl-C para sair)")

    try:
        while True:
            data = stream.read(CHUNK_SAMPLES, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)
            predictions = model.predict(frame)
            score = predictions.get(model_key, 0.0)
            if score >= args.threshold:
                logger.info("DETECTADA (score=%.3f)", score)
            elif score >= args.threshold * 0.5:
                logger.info("score=%.3f", score)
    except KeyboardInterrupt:
        logger.info("Encerrando.")
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    main()
