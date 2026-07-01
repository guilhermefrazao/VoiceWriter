import re
import logging


def _normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """WER = (S + D + I) / N palavras de referência. Pode ultrapassar 1.0."""
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
    """CER = Levenshtein em nível de caractere / len(referência)."""
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


def wer_breakdown(reference: str, hypothesis: str) -> dict:
    """
    Decompõe o WER em taxas individuais: substituições, deleções, inserções.
    Útil para diagnóstico: o modelo troca palavras, perde ou inventa?
    Todas as taxas são normalizadas pelo número de palavras da referência.
    """
    ref = _normalize(reference)
    hyp = _normalize(hypothesis)
    n = len(ref)
    m = len(hyp)

    if n == 0:
        ins = m / 1 if m > 0 else 0.0
        return {"substitutions": 0.0, "deletions": 0.0, "insertions": ins}

    # Matriz DP completa para traceback
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])

    # Traceback para contar operações
    subs = dels = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            subs += 1
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            dels += 1
            i -= 1
        else:
            ins += 1
            j -= 1

    return {
        "substitutions": round(subs / n, 4),
        "deletions": round(dels / n, 4),
        "insertions": round(ins / n, 4),
    }


def normalized_wer(reference: str, hypothesis: str) -> float:
    """
    WER calculado após normalização: lowercase + remoção de pontuação.
    Permite comparação justa entre modelos com estilos de pontuação diferentes
    (Whisper pontua agressivamente; outros modelos não pontuam).
    """
    return word_error_rate(reference, hypothesis)


def bleu_score(reference: str, hypothesis: str) -> float:
    """
    BLEU score com smoothing (método 1). Captura fluência em frases longas.
    Complementa WER: WER detecta erros locais; BLEU captura qualidade global.
    Retorna 0.0 se NLTK não estiver instalado.
    """
    try:
        from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    except ImportError:
        logging.warning("[ASR Metrics] nltk não instalado — BLEU score indisponível.")
        return 0.0

    ref_tokens = _normalize(reference)
    hyp_tokens = _normalize(hypothesis)
    if not ref_tokens or not hyp_tokens:
        return 0.0

    smoother = SmoothingFunction().method1
    return round(sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoother), 4)


def success_rate(results: list[bool]) -> float:
    """Fração de comandos bem-sucedidos com base no feedback explícito do usuário."""
    if not results:
        return 0.0
    return sum(results) / len(results)


def latency(start: float, end: float) -> float:
    """Latência da transcrição em milissegundos."""
    return (end - start) * 1_000.0


def real_time_factor(latency_s: float, audio_duration_s: float) -> float:
    """RTF = latência / duração do áudio. RTF < 1.0 = mais rápido que tempo real."""
    if audio_duration_s <= 0:
        return float("inf")
    return latency_s / audio_duration_s


def avg_word_confidence(segments) -> float | None:
    """
    Confiança média por palavra a partir dos segmentos do faster-whisper.
    Requer word_timestamps=True no model.transcribe(). Retorna None se indisponível.
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
    cold_start: bool = False,
    peak_memory_mb: float | None = None,
) -> dict:
    """
    Agrega todas as métricas de uma transcrição em um dict pronto para salvar.

    Args:
        hypothesis:       texto transcrito pelo modelo
        reference:        texto de referência para WER/CER/BLEU (None em modo orgânico)
        start_time:       time.time() antes de model.transcribe()
        end_time:         time.time() após model.transcribe()
        audio_duration_s: duração do áudio em segundos para RTF
        segments:         segmentos do faster-whisper (para confiança por palavra)
        cold_start:       True se é a primeira inferência da sessão
        peak_memory_mb:   pico de memória GPU/RAM durante a inferência
    """
    lat_ms = latency(start_time, end_time) if start_time is not None and end_time is not None else None

    wer = word_error_rate(reference, hypothesis or "") if reference else None
    cer = character_error_rate(reference, hypothesis or "") if reference else None
    breakdown = wer_breakdown(reference, hypothesis or "") if reference else None
    nwer = normalized_wer(reference, hypothesis or "") if reference else None
    bleu = bleu_score(reference, hypothesis or "") if reference else None
    rtf = real_time_factor(lat_ms / 1_000.0, audio_duration_s) if lat_ms is not None and audio_duration_s else None
    confidence = avg_word_confidence(segments) if segments else None

    result = {
        "transcribed_text":   hypothesis,
        "reference_text":     reference,
        "latency_ms":         round(lat_ms, 2) if lat_ms is not None else None,
        "wer":                round(wer, 4) if wer is not None else None,
        "cer":                round(cer, 4) if cer is not None else None,
        "wer_normalized":     round(nwer, 4) if nwer is not None else None,
        "wer_substitutions":  breakdown["substitutions"] if breakdown else None,
        "wer_deletions":      breakdown["deletions"] if breakdown else None,
        "wer_insertions":     breakdown["insertions"] if breakdown else None,
        "bleu_score":         bleu,
        "rtf":                round(rtf, 4) if rtf is not None else None,
        "avg_confidence":     round(confidence, 4) if confidence is not None else None,
        "cold_start":         cold_start,
        "peak_memory_mb":     round(peak_memory_mb, 1) if peak_memory_mb is not None else None,
        "is_benchmark":       reference is not None,
    }

    parts = []
    if lat_ms is not None:
        parts.append(f"latency={lat_ms:.0f}ms")
    if wer is not None:
        parts.append(f"WER={wer:.2%}")
    if cer is not None:
        parts.append(f"CER={cer:.2%}")
    if bleu is not None:
        parts.append(f"BLEU={bleu:.3f}")
    if rtf is not None:
        parts.append(f"RTF={rtf:.3f}")
    if confidence is not None:
        parts.append(f"conf={confidence:.2%}")

    if parts:
        logging.info("[ASR Metrics] " + " | ".join(parts))

    return result
