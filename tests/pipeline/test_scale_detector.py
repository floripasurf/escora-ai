from src.parser.scale_detector import detect_scale_from_texts


def test_detect_1_50():
    texts = ["PLANTA DE FORMAS", "ESC 1:50", "NIVEL +3.00"]
    assert detect_scale_from_texts(texts) == 0.02  # 1/50


def test_detect_1_25():
    texts = ["ESCALA 1:25", "COBERTURA"]
    assert detect_scale_from_texts(texts) == 0.04  # 1/25


def test_detect_1_100():
    texts = ["ESC.: 1/100"]
    assert detect_scale_from_texts(texts) == 0.01  # 1/100


def test_no_scale_returns_none():
    texts = ["PLANTA DE FORMAS", "NIVEL +3.00"]
    assert detect_scale_from_texts(texts) is None


def test_detect_case_insensitive():
    texts = ["esc 1:50"]
    assert detect_scale_from_texts(texts) == 0.02
