import pytest
from src.models.confidence import calculate_confidence


def test_both_signals_agree():
    """Geometry says beam (0.85), text says beam (0.90) -> high confidence."""
    score = calculate_confidence(score_geo=0.85, score_txt=0.90, agree=True)
    assert score == min(max(0.85, 0.90) + 0.10, 1.0)  # 1.0 (capped)


def test_both_signals_contradict():
    """Geometry says beam (0.80), text says pillar (0.70) -> low confidence."""
    score = calculate_confidence(score_geo=0.80, score_txt=0.70, agree=False)
    assert score == max(min(0.80, 0.70) - 0.20, 0.0)  # 0.50


def test_only_geometric_signal():
    """Only geometry signal (0.85), no text -> moderate confidence."""
    score = calculate_confidence(score_geo=0.85, score_txt=0.0, agree=True)
    assert score == pytest.approx(0.85 * 0.85)  # 0.7225


def test_only_textual_signal():
    """Only text signal (0.90), no geometry -> moderate confidence."""
    score = calculate_confidence(score_geo=0.0, score_txt=0.90, agree=True)
    assert score == pytest.approx(0.90 * 0.85)  # 0.765


def test_no_signal():
    """No signals at all -> zero confidence."""
    score = calculate_confidence(score_geo=0.0, score_txt=0.0, agree=True)
    assert score == 0.0


def test_cap_at_1():
    """Both signals at 0.95 -> capped at 1.0."""
    score = calculate_confidence(score_geo=0.95, score_txt=0.95, agree=True)
    assert score == 1.0


def test_floor_at_0():
    """Contradicting low signals -> floored at 0.0."""
    score = calculate_confidence(score_geo=0.15, score_txt=0.10, agree=False)
    assert score == 0.0
