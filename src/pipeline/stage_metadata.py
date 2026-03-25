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
