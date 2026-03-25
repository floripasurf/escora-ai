"""Confidence score calculation for element classification.

Two independent signals (geometric + textual) are combined:
- Both agree: max(geo, txt) + 0.10 (capped at 1.0)
- Both contradict: min(geo, txt) - 0.20 (floored at 0.0)
- Only one signal: available_score * 0.85
"""

AGREE_BONUS = 0.10
CONTRADICT_PENALTY = 0.20
SINGLE_SIGNAL_FACTOR = 0.85
SIGNAL_THRESHOLD = 0.05


def calculate_confidence(
    score_geo: float,
    score_txt: float,
    agree: bool,
) -> float:
    has_geo = score_geo >= SIGNAL_THRESHOLD
    has_txt = score_txt >= SIGNAL_THRESHOLD

    if not has_geo and not has_txt:
        return 0.0

    if has_geo and has_txt:
        if agree:
            return min(max(score_geo, score_txt) + AGREE_BONUS, 1.0)
        else:
            return max(min(score_geo, score_txt) - CONTRADICT_PENALTY, 0.0)

    available = score_geo if has_geo else score_txt
    return available * SINGLE_SIGNAL_FACTOR
