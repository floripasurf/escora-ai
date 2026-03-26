"""Persistent learning store — accumulates knowledge across DXF runs.

After each pipeline run, a LearningRecord is saved with detection stats,
layer classifications, section patterns, and confidence distributions.
On subsequent runs, accumulated knowledge adjusts detection behavior:
- Layer names that consistently map to beams/pillars get priority
- Common section dimensions become fallback defaults
- Confidence thresholds adapt based on historical accuracy
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path("data/learning.json")


@dataclass
class LayerLearning:
    """What was found on a specific DXF layer."""
    layer_name: str
    beam_count: int = 0
    pillar_count: int = 0
    segment_count: int = 0
    rect_count: int = 0
    detection_rate: float = 0.0


@dataclass
class LearningRecord:
    """Snapshot of what was learned from a single DXF run."""
    filename: str
    timestamp: str
    scale: float

    # Detection counts
    beam_count: int = 0
    pillar_count: int = 0
    slab_count: int = 0

    # Beams with/without text matches
    beams_with_name: int = 0
    beams_with_section: int = 0
    beams_estimated_height: int = 0

    # Score distributions (buckets: 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    beam_score_avg: float = 0.0
    pillar_score_avg: float = 0.0

    # Layer classifications observed
    layers: List[dict] = field(default_factory=list)

    # Section dimensions seen (e.g. {"14x40": 12, "19x60": 5})
    section_freq: Dict[str, int] = field(default_factory=dict)

    # Layer name → element type mapping learned
    layer_element_map: Dict[str, str] = field(default_factory=dict)

    # Metadata found
    pe_direito_m: Optional[float] = None
    slab_thickness_m: Optional[float] = None
    pe_direito_found: bool = False
    slab_thickness_found: bool = False

    # Calculation results
    total_shores: int = 0
    total_load_kn: float = 0.0
    is_valid: bool = True
    warning_count: int = 0
    error_count: int = 0


class LearningStore:
    """Persistent store for learning records."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_STORE_PATH
        self._records: List[LearningRecord] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._records = [
                    LearningRecord(**r) for r in data.get("records", [])
                ]
                logger.info(f"Loaded {len(self._records)} learning records")
            except Exception as e:
                logger.warning(f"Failed to load learning store: {e}")
                self._records = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "updated": datetime.now().isoformat(),
            "record_count": len(self._records),
            "records": [asdict(r) for r in self._records],
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def add(self, record: LearningRecord):
        self._records.append(record)
        self.save()
        logger.info(
            f"Learning record added: {record.filename} "
            f"({record.beam_count} beams, {record.pillar_count} pillars)"
        )

    @property
    def records(self) -> List[LearningRecord]:
        return self._records

    @property
    def run_count(self) -> int:
        return len(self._records)

    # === LEARNED KNOWLEDGE QUERIES ===

    def get_known_beam_layers(self) -> Dict[str, float]:
        """Layers that historically contained beams, with confidence (0-1).

        Returns {layer_name: confidence} where confidence is the fraction
        of runs where that layer had beam candidates.
        """
        layer_beam_counts: Counter = Counter()
        layer_appearances: Counter = Counter()

        for r in self._records:
            seen_layers = set()
            for layer in r.layers:
                name = layer["layer_name"]
                if name not in seen_layers:
                    layer_appearances[name] += 1
                    seen_layers.add(name)
                if layer.get("beam_count", 0) > 0:
                    layer_beam_counts[name] += 1

        result = {}
        for layer, count in layer_beam_counts.items():
            total = layer_appearances[layer]
            result[layer] = count / total if total > 0 else 0
        return result

    def get_known_pillar_layers(self) -> Dict[str, float]:
        """Layers that historically contained pillars, with confidence."""
        layer_pillar_counts: Counter = Counter()
        layer_appearances: Counter = Counter()

        for r in self._records:
            seen_layers = set()
            for layer in r.layers:
                name = layer["layer_name"]
                if name not in seen_layers:
                    layer_appearances[name] += 1
                    seen_layers.add(name)
                if layer.get("pillar_count", 0) > 0:
                    layer_pillar_counts[name] += 1

        result = {}
        for layer, count in layer_pillar_counts.items():
            total = layer_appearances[layer]
            result[layer] = count / total if total > 0 else 0
        return result

    def get_common_sections(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Most common beam section dimensions across all runs.

        Returns [(section_str, total_count), ...] sorted by frequency.
        """
        total: Counter = Counter()
        for r in self._records:
            for section, count in r.section_freq.items():
                total[section] += count
        return total.most_common(top_n)

    def get_default_section_height(self) -> Optional[float]:
        """Most common section height from historical data.

        Returns height in meters, or None if no data.
        """
        height_counts: Counter = Counter()
        for r in self._records:
            for section, count in r.section_freq.items():
                parts = section.split("x")
                if len(parts) == 2:
                    try:
                        h_cm = int(parts[1])
                        height_counts[h_cm] += count
                    except ValueError:
                        pass
        if not height_counts:
            return None
        most_common_cm = height_counts.most_common(1)[0][0]
        return most_common_cm / 100.0

    def get_avg_beam_score(self) -> Optional[float]:
        """Average beam confidence score across all runs."""
        scores = [r.beam_score_avg for r in self._records if r.beam_score_avg > 0]
        return sum(scores) / len(scores) if scores else None

    def get_pe_direito_history(self) -> Optional[float]:
        """Most commonly found pé-direito value."""
        values: Counter = Counter()
        for r in self._records:
            if r.pe_direito_found and r.pe_direito_m is not None:
                values[round(r.pe_direito_m, 2)] += 1
        if not values:
            return None
        return values.most_common(1)[0][0]

    def summary(self) -> str:
        """Human-readable summary of accumulated knowledge."""
        if not self._records:
            return "Nenhum dado de aprendizado acumulado."

        lines = [
            f"=== Escora.AI — Base de Aprendizado ===",
            f"Total de execuções: {len(self._records)}",
            f"Arquivos processados: {len(set(r.filename for r in self._records))}",
            "",
        ]

        # Common sections
        sections = self.get_common_sections(8)
        if sections:
            lines.append("Seções mais frequentes:")
            for section, count in sections:
                lines.append(f"  {section} cm — {count}x")
            lines.append("")

        # Known layers
        beam_layers = self.get_known_beam_layers()
        if beam_layers:
            lines.append("Layers com vigas (confiança):")
            for layer, conf in sorted(beam_layers.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"  \"{layer}\" — {conf:.0%}")
            lines.append("")

        pillar_layers = self.get_known_pillar_layers()
        if pillar_layers:
            lines.append("Layers com pilares (confiança):")
            for layer, conf in sorted(pillar_layers.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"  \"{layer}\" — {conf:.0%}")
            lines.append("")

        # Stats
        total_beams = sum(r.beam_count for r in self._records)
        total_pillars = sum(r.pillar_count for r in self._records)
        total_shores = sum(r.total_shores for r in self._records)
        lines.append(f"Totais acumulados:")
        lines.append(f"  Vigas detectadas: {total_beams}")
        lines.append(f"  Pilares detectados: {total_pillars}")
        lines.append(f"  Escoras calculadas: {total_shores}")

        pe = self.get_pe_direito_history()
        if pe:
            lines.append(f"  Pé-direito mais comum: {pe:.2f}m")

        default_h = self.get_default_section_height()
        if default_h:
            lines.append(f"  Altura de seção mais comum: {default_h:.2f}m")

        return "\n".join(lines)
