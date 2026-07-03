"""Loop de detecção de wakeword. Duas wakewords pré-treinadas do openWakeWord,
cada uma disparando um modo diferente:
  - "hey_jarvis" -> transcrição contínua para o cursor (voice.type_at_cursor)
  - "alexa"      -> um único comando (abrir/fechar app, desligar), igual ao F8

Ambas rodam no mesmo stream de microfone (mesmo Model, várias wakewords), então
nunca há duas escutas concorrentes disputando o dispositivo de áudio.
"""
import logging
from typing import Callable

import numpy as np
import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms @ 16kHz
THRESHOLD = 0.7


def _start_type_at_cursor() -> None:
    from voice.type_at_cursor import TypeAtCursorMode

    TypeAtCursorMode().run()


def _run_command() -> None:
    from voice.speech import SpeechToText

    SpeechToText().listen_for_command()


WAKEWORD_CALLBACKS: dict[str, Callable[[], None]] = {
    "hey_jarvis": _start_type_at_cursor,
    "alexa": _run_command,
}


def _download_builtin_models(model_names: list[str]) -> None:
    from openwakeword.utils import download_models

    builtin_names = [
        name for name in model_names
        if "/" not in name and "\\" not in name and not name.endswith((".onnx", ".tflite"))
    ]
    if builtin_names:
        download_models(builtin_names)


def _wait_for_detection(model, threshold: float) -> str:
    """Abre seu próprio stream de microfone e bloqueia até alguma wakeword
    passar de `threshold`. Libera o stream ao retornar (nome detectado), para
    que o callback disparado em seguida possa abrir o microfone sem conflito
    de dispositivo.
    """
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SAMPLES,
    )
    logger.info("Microfone aberto, detecção de wakeword pode começar")
    try:
        while True:
            data = stream.read(CHUNK_SAMPLES, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)
            predictions = model.predict(frame)
            for name, score in predictions.items():
                if score >= threshold:
                    logger.info("Wakeword '%s' detectada (score=%.3f)", name, score)
                    return name
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def wakeword_loop(
    wakeword_callbacks: dict[str, Callable[[], None]] | None = None,
    threshold: float = THRESHOLD,
) -> None:
    from openwakeword.model import Model

    wakeword_callbacks = wakeword_callbacks or WAKEWORD_CALLBACKS
    model_names = list(wakeword_callbacks.keys())

    _download_builtin_models(model_names)
    model = Model(wakeword_models=model_names, inference_framework="onnx")
    logger.info("Wakeword listener iniciado (modelos=%s, limiar=%.2f)", model_names, threshold)

    while True:
        detected_name = _wait_for_detection(model, threshold)
        wakeword_callbacks[detected_name]()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    wakeword_loop()
