"""
Matching fonético para nomes de app em comandos de voz.

Casa o texto transcrito (frequentemente distorcido pelo sotaque PT-BR em nomes
ingleses, ex: "steam" -> "istim") contra uma lista de candidatos conhecidos,
usando um esqueleto consonantal (a distorção do sotaque se concentra nas
vogais - epêntese, mudança de qualidade vocálica) comparado por distância de
edição, com janela deslizante de tokens para tolerar texto residual do regex
de comando (ex: "abra o chrome por favor" -> tenta "chrome" isoladamente).

Ver .specs/research-command-phonetics.md para a justificativa e validação.
"""

from dataclasses import dataclass

_VOWELS = set("aeiouáéíóúâêîôûãõàAEIOUÁÉÍÓÚÂÊÎÔÛÃÕÀ")

_DIGRAPHS = [
    ("ck", "k"),
    ("qu", "k"),
    ("ph", "f"),
    ("th", "t"),
    ("x", "ks"),
    ("c", "k"),
    ("y", "i"),
    ("w", "u"),
]


def consonant_skeleton(text: str) -> str:
    s = text.lower().strip()
    s = "".join(ch for ch in s if ch.isalpha() or ch.isspace())
    s = s.replace(" ", "")

    for src, dst in _DIGRAPHS:
        s = s.replace(src, dst)

    consonants = [ch for ch in s if ch not in _VOWELS]

    collapsed = []
    for ch in consonants:
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)

    return "".join(collapsed)


def _levenshtein(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[:]
        dp[0] = i
        for j, cb in enumerate(b, 1):
            dp[j] = prev[j - 1] if ca == cb else 1 + min(prev[j], dp[j - 1], prev[j - 1])
    return dp[len(b)]


def _similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1.0 - _levenshtein(a, b) / max(len(a), len(b), 1)


@dataclass
class MatchResult:
    name: str | None
    score: float
    matched_window: str | None


# Um catálogo real de apps instalados tem 50-300 entradas (vs. 10 no teste do
# protótipo), então o risco de colisão por esqueleto curto é maior — mas
# banir esqueletos curtos direto (ex: exigir >=4 caracteres) also bane nomes
# legítimos como "steam" (esqueleto "stm", só 3 chars — o próprio exemplo
# motivador da tarefa). Em vez disso, o limiar de confiança escala com o
# tamanho do esqueleto: quanto mais curto, mais perto de exato precisa ser
# (menos "espaço" pra tolerar diferença sem virar coincidência). Ver
# .specs/research-command-phonetics.md.
DEFAULT_MIN_SCORE = 0.82


def _required_score(skeleton_len: int, base_min_score: float) -> float:
    if skeleton_len <= 2:
        return 1.01  # esqueleto quase vazio: nunca confia, mesmo em match "exato"
    if skeleton_len <= 4:
        return max(base_min_score, 0.95)  # só aceita quase-exato
    return base_min_score


def best_match(
    spoken_tail: str,
    candidates: dict[str, str],
    min_score: float = DEFAULT_MIN_SCORE,
) -> MatchResult:
    """
    spoken_tail: texto depois do verbo de comando (ex: "chrome por favor").
    candidates:  dict {nome_de_exibição: <qualquer valor associado>} — só as
                 chaves são usadas para o matching.
    """
    tokens = spoken_tail.lower().split()
    if not tokens or not candidates:
        return MatchResult(name=None, score=0.0, matched_window=None)

    candidate_skeletons = {name: consonant_skeleton(name) for name in candidates}

    # Só pra log/diagnóstico quando nada passa no limiar (mostra o quão perto chegou).
    best_overall = MatchResult(name=None, score=0.0, matched_window=None)

    # O vencedor de fato: entre os candidatos que passam no PRÓPRIO limiar
    # (ajustado pelo tamanho do esqueleto), o de maior margem acima do limiar.
    best_passing: MatchResult | None = None
    best_margin = -1.0

    for window_len in range(1, len(tokens) + 1):
        window = " ".join(tokens[:window_len])
        window_skel = consonant_skeleton(window)
        if not window_skel:
            continue
        for name, cand_skel in candidate_skeletons.items():
            if not cand_skel:
                continue
            score = _similarity(window_skel, cand_skel)

            if score > best_overall.score:
                best_overall = MatchResult(name=name, score=score, matched_window=window)

            required = _required_score(min(len(window_skel), len(cand_skel)), min_score)
            margin = score - required
            if margin >= 0 and margin > best_margin:
                best_margin = margin
                best_passing = MatchResult(name=name, score=score, matched_window=window)

    if best_passing:
        return best_passing
    return MatchResult(name=None, score=best_overall.score, matched_window=best_overall.matched_window)
