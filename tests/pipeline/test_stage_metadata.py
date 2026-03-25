import pytest
from src.pipeline.stage_metadata import extract_pe_direito, extract_level_height
from src.pipeline.stage_parse import TextEntity


def test_extract_pe_direito():
    texts = [
        TextEntity("PE DIREITO 2.92m", 10, 10, "TEXTO"),
        TextEntity("V1 14x40", 5, 5, "TEXTO"),
    ]
    assert extract_pe_direito(texts) == pytest.approx(2.92)


def test_extract_pe_direito_pattern2():
    texts = [TextEntity("PD=2.80", 10, 10, "TEXTO")]
    assert extract_pe_direito(texts) == pytest.approx(2.80)


def test_pe_direito_not_found():
    texts = [TextEntity("V1 14x40", 5, 5, "TEXTO")]
    assert extract_pe_direito(texts) is None


def test_extract_level():
    texts = [TextEntity("NIVEL +1330.40", 10, 10, "TEXTO")]
    assert extract_level_height(texts) == pytest.approx(1330.40)
