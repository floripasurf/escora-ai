"""Detect drawing scale from text annotations in DXF.

Searches for patterns like 'ESC 1:50', 'ESCALA 1:25', 'ESC.: 1/100'.
Returns scale factor: DXF_units * factor = meters.
"""

import re
from typing import List, Optional

SCALE_PATTERN = re.compile(
    r"ESC(?:ALA)?[\s.:]*1\s*[:/]\s*(\d+)",
    re.IGNORECASE,
)


def detect_scale_from_texts(texts: List[str]) -> Optional[float]:
    for text in texts:
        match = SCALE_PATTERN.search(text)
        if match:
            denominator = int(match.group(1))
            if denominator > 0:
                return 1.0 / denominator
    return None
