"""Classify structural elements from DXF text content and layer names.

Patterns detected:
- Beams: V\\d+, VG\\d+, VIGA
- Pillars: P\\d+, PIL, PILAR
- Slabs: L\\d+, LAJE, LJ
- Sections: \\d+x\\d+, \\d+/\\d+
- Thickness: h=\\d+, e=\\d+cm, ESP
"""

import re
from typing import Optional, Tuple
from dataclasses import dataclass
from src.models.pipeline_models import ElementType


@dataclass
class TextClassification:
    element_type: ElementType
    name: Optional[str]
    score: float


BEAM_PATTERNS = [
    (re.compile(r"\bVIGA\s*\d*\w*", re.IGNORECASE), 0.95),
    (re.compile(r"\bVG[-.]?\d+", re.IGNORECASE), 0.90),
    (re.compile(r"\bV\d+\w*\b", re.IGNORECASE), 0.85),  # case-insensitive: v1 = V1
    (re.compile(r"\bVIGAS?\b", re.IGNORECASE), 0.80),
]

PILLAR_PATTERNS = [
    (re.compile(r"\bPILAR\s*\d*\w*", re.IGNORECASE), 0.95),
    (re.compile(r"\bPIL[-.]?\d+", re.IGNORECASE), 0.90),
    (re.compile(r"\bP\d+\w*\b", re.IGNORECASE), 0.85),  # case-insensitive: p70 = P70 (Cesar/ALG)
    (re.compile(r"\bPILARES?\b", re.IGNORECASE), 0.80),
]

SLAB_PATTERNS = [
    (re.compile(r"\bLAJE\s*\d*\w*", re.IGNORECASE), 0.95),
    (re.compile(r"\bLJ[-.]?\d+", re.IGNORECASE), 0.90),
    (re.compile(r"\bL\d+\w*\b", re.IGNORECASE), 0.85),  # case-insensitive: l1 = L1
    (re.compile(r"\bLAJES?\b", re.IGNORECASE), 0.80),
]

SECTION_PATTERN = re.compile(r"(\d+)\s*[x/]\s*(\d+)")
THICKNESS_PATTERN = re.compile(r"(?:[he]=?\s*|ESP\.?\s*)(\d+)\s*(?:cm)?", re.IGNORECASE)


def classify_text(text: str) -> TextClassification:
    for pattern, score in BEAM_PATTERNS:
        m = pattern.search(text)
        if m:
            return TextClassification(ElementType.BEAM, m.group(0).strip(), score)

    for pattern, score in PILLAR_PATTERNS:
        m = pattern.search(text)
        if m:
            return TextClassification(ElementType.PILLAR, m.group(0).strip(), score)

    for pattern, score in SLAB_PATTERNS:
        m = pattern.search(text)
        if m:
            return TextClassification(ElementType.SLAB, m.group(0).strip(), score)

    return TextClassification(ElementType.UNKNOWN, None, 0.0)


def extract_section(text: str) -> Optional[Tuple[float, float]]:
    m = SECTION_PATTERN.search(text)
    if m:
        w_cm = int(m.group(1))
        h_cm = int(m.group(2))
        return (w_cm / 100.0, h_cm / 100.0)
    return None


def extract_thickness(text: str) -> Optional[float]:
    m = THICKNESS_PATTERN.search(text)
    if m:
        value = int(m.group(1))
        if value < 100:
            return value / 100.0
        return value / 1000.0
    return None
