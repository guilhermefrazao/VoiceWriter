import re
import time
import logging
import functools


def _normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """
    WER = (Substituições + Deleções + Inserções) / N palavras de referência.
    Usa Levenshtein em nível de palavra. Pode ultrapassar 1.0.
    """
    ref = _normalize(reference)
    hyp = _normalize(hypothesis)

    n = len(ref)
    if n == 0:
        return 0.0 if not hyp else float("inf")

    dp = list(range(len(hyp) + 1))
    for i, r_word in enumerate(ref, 1):
        prev = dp[:]
        dp[0] = i
        for j, h_word in enumerate(hyp, 1):
            dp[j] = prev[j - 1] if r_word == h_word else 1 + min(prev[j], dp[j - 1], prev[j - 1])

    return dp[len(hyp)] / n


def character_error_rate(reference: str, hypothesis: str) -> float:
    """
    CER = Levenshtein em nível de caractere / len(referência).
    Mais sensível que WER para palavras compostas ou erros parciais.
    """
    ref = reference.lower().replace(" ", "")
    hyp = hypothesis.lower().replace(" ", "")

    n = len(ref)
    if n == 0:
        return 0.0 if not hyp else float("inf")

    dp = list(range(len(hyp) + 1))
    for i, r_char in enumerate(ref, 1):
        prev = dp[:]
        dp[0] = i
        for j, h_char in enumerate(hyp, 1):
            dp[j] = prev[j - 1] if r_char == h_char else 1 + min(prev[j], dp[j - 1], prev[j - 1])

    return dp[len(hyp)] / n


def success_rate(results: list[bool]) -> float:
    """
    Fração de comandos bem-sucedidos com base no feedback explícito do usuário.
    Cada elemento é True (sucesso confirmado) ou False (falha reportada).
    """
    if not results:
        return 0.0
    return sum(results) / len(results)


def latency(start: float, end: float) -> float:
    """Latência da transcrição em milissegundos."""
    return (end - start) * 1_000.0


def real_time_factor(latency_s: float, audio_duration_s: float) -> float:
    """
    RTF = latência / duração do áudio.
    RTF < 1.0 significa processamento mais rápido que tempo real.
    """
    if audio_duration_s <= 0:
        return float("inf")
    return latency_s / audio_duration_s


def avg_word_confidence(segments) -> float | None:
    """
    Confiança média por palavra a partir dos segmentos.
    Requer word_timestamps=True no model.transcribe().
    Retorna None se os segmentos não tiverem dados de palavra.
    """
    scores = []
    for segment in segments:
        if hasattr(segment, "words") and segment.words:
            scores.extend(w.probability for w in segment.words)
    return sum(scores) / len(scores) if scores else None


def analyze_transcription(
    hypothesis: str | None,
    reference: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    audio_duration_s: float | None = None,
    segments=None,
) -> dict:
    """
    Agrega todas as métricas de uma transcrição e registra no log.

    Args:
        hypothesis:    texto transcrito (None ou vazio = sem resultado)
        user_success:  feedback explícito do usuário via popup (True/False/None)
        reference:     texto de referência para WER/CER (opcional)
        start_time:    time.time() antes de model.transcribe() — opcional quando
                       @time_transcription já loga a latência
        end_time:      time.time() após model.transcribe() (opcional)
        audio_duration_s: duração do áudio em segundos para RTF (opcional)
        segments:      segmentos do faster-whisper para confiança (opcional)
    """
    lat_ms = latency(start_time, end_time)

    wer = word_error_rate(reference, hypothesis or "") if reference else None
    cer = character_error_rate(reference, hypothesis or "") if reference else None
    rtf = real_time_factor(lat_ms / 1_000.0, audio_duration_s) 
    confidence = avg_word_confidence(segments) if segments else None

    result = {
        "latency_ms":     round(lat_ms, 2) if lat_ms is not None else None,
        "wer":            round(wer, 4) if wer is not None else None,
        "cer":            round(cer, 4) if cer is not None else None,
        "rtf":            round(rtf, 4) if rtf is not None else None,
        "avg_confidence": round(confidence, 4) if confidence is not None else None,
    }

    parts = []

    if lat_ms is not None:
        parts.append(f"latency={lat_ms:.0f}ms")
    if wer is not None:
        parts.append(f"WER={wer:.2%}")
    if cer is not None:
        parts.append(f"CER={cer:.2%}")
    if rtf is not None:
        parts.append(f"RTF={rtf:.3f}")
    if confidence is not None:
        parts.append(f"confidence={confidence:.2%}")

    if parts:
        logging.info("[ASR Metrics] " + " | ".join(parts))

    return result
