"""Stage 4: Extract metadata from text annotations.

Searches for floor height (pe-direito), level heights, and associates
section/thickness data with already-classified elements.
"""

import re
from typing import List, Optional
from src.pipeline.stage_parse import TextEntity

PE_DIREITO_PATTERN = re.compile(
    r"(?:P[EÉ]\s*DIR(?:EITO)?|PD)\s*[=:]?\s*(\d+[.,]\d+)\s*m?",
    re.IGNORECASE,
)

LEVEL_HEIGHT_PATTERN = re.compile(
    r"(?:N[IÍ]VEL|COTA|N)\s*[\+\-]?\s*(\d{2,}[.,]?\d*)",
    re.IGNORECASE,
)


def extract_pe_direito(texts: List[TextEntity]) -> Optional[float]:
    for t in texts:
        m = PE_DIREITO_PATTERN.search(t.content)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def extract_level_height(texts: List[TextEntity]) -> Optional[float]:
    for t in texts:
        m = LEVEL_HEIGHT_PATTERN.search(t.content)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


SLAB_THICKNESS_PATTERNS = (
    re.compile(
        r"\b[he]\s*[=:]\s*(\d+(?:[.,]\d+)?)\s*(?:cm|m)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bESP(?:ESSURA)?\s*[=:]?\s*(\d+(?:[.,]\d+)?)\s*(?:cm|m)?\b",
        re.IGNORECASE,
    ),
)


def extract_slab_thickness(texts: List[TextEntity]) -> Optional[float]:
    """Extract slab thickness from text annotations.

    Looks for patterns like h=12, e=15cm, ESP 10, ESPESSURA=20.
    Values > 1 are assumed to be in cm and converted to meters.
    Values <= 1 are assumed to already be in meters.

    Returns thickness in meters, or None if not found.
    """
    for t in texts:
        for pattern in SLAB_THICKNESS_PATTERNS:
            m = pattern.search(t.content)
            if m:
                value = float(m.group(1).replace(",", "."))
                if value > 1.0:
                    value /= 100.0  # cm to m
                return value
    return None
