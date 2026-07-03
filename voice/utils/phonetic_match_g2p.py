"""
Fase 3 do casamento fonético de comandos (.specs/research-command-phonetics.md,
§3, linha C) — versão baseada em G2P (grafema→fonema) real em vez do
esqueleto consonantal escrito à mão de phonetic_match.py.

Motivação: o esqueleto consonantal (tabela de dígrafos "ck"→"k", "ph"→"f",
etc.) precisa ser mantido manualmente e nunca generaliza para casos não
antecipados (ex: "ch" de "chrome" não virava "k" porque só a letra solta
"c" tinha regra, não o dígrafo "ch" — ver limitação documentada no
protótipo original). G2P elimina isso: usa modelos que já sabem as regras
reais de pronúncia do inglês (g2p_en, baseado no CMUdict) e do português
(epitran, baseado em regras fonológicas do idioma), sem tabela de exceções
mantida à mão.

Pipeline:
  1. Nome do app (inglês) → fonemas ARPABET via g2p_en → IPA (tabela de
     conversão ARPABET→IPA, um fato linguístico padrão, não heurística).
  2. Texto candidato (transcrito, ortografia "aportuguesada") → IPA direto
     via epitran (por-Latn) — já aplica as regras fonológicas do PT-BR
     (ex: "istim" → /iʃtĩ/, sozinho já reconhece que o -m final vira
     nasalização, não uma consoante).
  3. Ambos IPA são filtrados para manter só consoantes (via panphon,
     classificação fonética real por traço articulatório — não um crivo de
     caracteres escolhido à mão). Mesma lógica de phonetic_match.py (a
     distorção do sotaque se concentra nas vogais), mas aplicada em cima de
     fonemas de verdade, não letras.
  4. Comparação por distância fonética ponderada por traço articulatório
     (panphon.distance.Distance.weighted_feature_edit_distance_div_maxlen)
     — reconhece que /s/ e /ʃ/ são foneticamente próximos (both sibilantes
     surdas), por exemplo, o que uma distância de edição de caracteres não
     reconheceria.

Limiar calibrado empiricamente contra o benchmark real (ver
.specs/research/benchmark_g2p_vs_heuristic.py), não escolhido a dedo.
"""

import re
import threading
from dataclasses import dataclass
from functools import lru_cache

# Import + inicialização de panphon/g2p_en/epitran juntos custam ~2.4s
# (medido: panphon.FeatureTable ~450ms, panphon.distance.Distance ~240ms,
# g2p_en.G2p ~950ms, epitran.Epitran ~800ms) — inaceitável se pago a cada
# `import voice.interact_app` (regressão direta na tarefa 5 do Roberto,
# latência de inicialização). Tudo abaixo é carregado sob demanda (lazy),
# na primeira chamada real, não no import do módulo. `prewarm()` permite
# adiantar esse custo numa thread de fundo, no mesmo espírito do pre-warm
# do modelo ASR em main.py.
_lock = threading.Lock()
_ft = None
_dist = None
_g2p = None
_epi_pt = None


def _ensure_loaded() -> None:
    global _ft, _dist, _g2p, _epi_pt
    if _g2p is not None:
        return
    with _lock:
        if _g2p is not None:
            return
        import epitran
        import panphon
        import panphon.distance
        from g2p_en import G2p

        _ft = panphon.FeatureTable()
        _dist = panphon.distance.Distance()
        _g2p = G2p()
        _epi_pt = epitran.Epitran("por-Latn")


def prewarm() -> None:
    """Força o carregamento agora (chamar de uma thread de fundo no boot)."""
    _ensure_loaded()

# Tabela de conversão ARPABET -> IPA. Fato linguístico padrão (CMUdict usa
# ARPABET), não heurística de app específica — ao contrário da tabela de
# dígrafos em phonetic_match.py, esta não precisa crescer conforme surgem
# novos nomes de app.
_ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ",
    "HH": "h", "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n",
    "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t",
    "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}

_STRESS_DIGIT_RE = re.compile(r"[0-9]")


def _consonants_only(ipa_str: str) -> str:
    _ensure_loaded()
    segs = _ft.ipa_segs(ipa_str)
    out = []
    for seg in segs:
        fts = _ft.word_fts(seg)
        if fts and fts[0].get("cons") == 1:
            out.append(seg)
    return "".join(out)


@lru_cache(maxsize=2048)
def english_consonants(word: str) -> str:
    """Nome de app (inglês) -> sequência de consoantes IPA, via g2p_en."""
    _ensure_loaded()
    phones = [_STRESS_DIGIT_RE.sub("", p) for p in _g2p(word) if p.strip().isalpha() or p.strip().endswith(tuple("012"))]
    phones = [p for p in phones if p in _ARPABET_TO_IPA or _STRESS_DIGIT_RE.sub("", p) in _ARPABET_TO_IPA]
    ipa = "".join(_ARPABET_TO_IPA.get(p, "") for p in phones)
    return _consonants_only(ipa)


@lru_cache(maxsize=2048)
def portuguese_consonants(text: str) -> str:
    """Texto transcrito (ortografia PT-BR) -> sequência de consoantes IPA, via epitran."""
    _ensure_loaded()
    ipa = _epi_pt.transliterate(text)
    return _consonants_only(ipa)


def _phonetic_distance(target_ipa: str, candidate_ipa: str) -> float:
    """
    Menor = mais parecido. weighted_feature_edit_distance_div_maxlen já
    normaliza pelo comprimento em segmentos fonéticos internamente — NÃO
    dividir de novo pelo comprimento aqui (bug já cometido e corrigido: uma
    segunda normalização por len() infla artificialmente a similaridade de
    candidatos foneticamente longos, tipo "System Manager", mesmo quando o
    match é ruim). Ver .specs/research/benchmark_g2p_vs_heuristic.py.
    """
    if not target_ipa or not candidate_ipa:
        return float("inf")
    _ensure_loaded()
    return _dist.weighted_feature_edit_distance_div_maxlen(target_ipa, candidate_ipa)


@dataclass
class MatchResult:
    name: str | None
    distance: float
    matched_window: str | None


# Calibrado empiricamente contra o benchmark real de comandos (não escolhido
# a dedo) — ver .specs/research/benchmark_g2p_vs_heuristic.py e
# .specs/research-command-phonetics.md §5.4. A varredura de limiar mostrou
# sobreposição real entre distância de match correto e incorreto: não existe
# um limiar que zere falso positivo E maximize acerto ao mesmo tempo. Este
# valor (1.2) é o mais alto que ainda preserva 0 falso positivo nos casos
# negativos testados — pensado para uso como FALLBACK depois da heurística
# de phonetic_match.py, não como matcher primário isolado (nesse papel,
# limiares mais soltos como 3.0+ dão mais acerto bruto mas introduzem falso
# positivo, inaceitável como primeira linha).
DEFAULT_MAX_DISTANCE = 1.2


def best_match(
    spoken_tail: str,
    candidates: dict[str, str],
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> MatchResult:
    """
    Mesma interface de voice.utils.phonetic_match.best_match() — janela
    deslizante de tokens a partir do início de spoken_tail (tolera texto
    residual do regex, ex: "chrome por favor"), mas comparando por G2P +
    distância fonética em vez de esqueleto consonantal ortográfico.
    """
    tokens = spoken_tail.lower().split()
    if not tokens or not candidates:
        return MatchResult(name=None, distance=float("inf"), matched_window=None)

    candidate_ipa = {name: english_consonants(name) for name in candidates}

    best = MatchResult(name=None, distance=float("inf"), matched_window=None)

    for window_len in range(1, len(tokens) + 1):
        window = " ".join(tokens[:window_len])
        window_ipa = portuguese_consonants(window)
        if not window_ipa:
            continue
        for name, cand_ipa in candidate_ipa.items():
            if not cand_ipa:
                continue
            dist = _phonetic_distance(cand_ipa, window_ipa)
            if dist < best.distance:
                best = MatchResult(name=name, distance=dist, matched_window=window)

    if best.distance > max_distance:
        return MatchResult(name=None, distance=best.distance, matched_window=best.matched_window)
    return best
