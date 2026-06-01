"""Persistent learning store — accumulates knowledge across DXF runs.

After each pipeline run, a LearningRecord is saved with detection stats,
layer classifications, section patterns, and confidence distributions.
On subsequent runs, accumulated knowledge adjusts detection behavior:
- Layer names that consistently map to beams/pillars get priority
- Common section dimensions become fallback defaults
- Confidence thresholds adapt based on historical accuracy

V2 improvements:
- Per-file deduplication: only the LATEST run per filename is kept
- Per-file weighting: each unique file counts once (not 300x)
- Temporal decay: recent runs have more weight than old ones
- Quality gates: minimum detection thresholds to store layer data
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


def _data_root() -> Path:
    return Path(os.environ.get("ESCORA_DATA_DIR", "./data"))


def _default_store_path() -> Path:
    return _data_root() / "learning.json"


def _branch_store_dir() -> Path:
    return _data_root() / "learning"


# Legacy constants — kept for backwards-compat imports, but resolved lazily.
DEFAULT_STORE_PATH = _default_store_path()
BRANCH_STORE_DIR = _branch_store_dir()

# Maximum records to keep (per-file dedup means this = max unique files)
MAX_RECORDS = 200

# Temporal decay: records older than this many days get halved weight
DECAY_DAYS = 30


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

    # Revision feedback (populated only after engineer uploads validated DXF)
    revision_uploaded: bool = False
    revision_beam_shore_delta: int = 0   # +N = under-shored, -N = over-shored
    revision_slab_shore_delta: int = 0
    revision_beam_match_rate: float = 0.0
    revision_slab_match_rate: float = 0.0
    revision_avg_position_error_m: float = 0.0
    revision_added_layers: Dict[str, int] = field(default_factory=dict)
    revision_removed_layers: Dict[str, int] = field(default_factory=dict)


class LearningStore:
    """Persistent store for learning records.

    V2: Per-file deduplication — only the latest run per filename is kept.
    This prevents a single file run 300x from dominating the knowledge base.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        branch_id: Optional[str] = None,
    ):
        """Create a learning store.

        - If `path` is given, it overrides everything (used by tests).
        - Else if `branch_id` is given, the store is scoped to
          `data/learning/{branch_id}.json`, keeping each locadora branch's
          knowledge isolated (engineer revisions from one branch do not
          bias density corrections on another).
        - Else the legacy single-tenant `data/learning.json` is used.
        """
        if path is not None:
            self.path = path
        elif branch_id:
            self.path = _branch_store_dir() / f"{branch_id}.json"
        else:
            self.path = _default_store_path()
        self.branch_id = branch_id
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
            "version": 2,
            "updated": datetime.now().isoformat(),
            "record_count": len(self._records),
            "unique_files": len(set(r.filename for r in self._records)),
            "records": [asdict(r) for r in self._records],
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def add(self, record: LearningRecord):
        """Add a record, replacing any previous run of the same file.

        Per-file deduplication: only the latest run per filename is kept.
        This prevents a file run 300x from having 300x the influence.
        """
        # Remove previous records for the same file
        self._records = [
            r for r in self._records if r.filename != record.filename
        ]
        self._records.append(record)

        # Cap total records
        if len(self._records) > MAX_RECORDS:
            # Keep most recent records
            self._records.sort(key=lambda r: r.timestamp)
            self._records = self._records[-MAX_RECORDS:]

        self.save()
        logger.info(
            f"Learning record added: {record.filename} "
            f"({record.beam_count} beams, {record.pillar_count} pillars, "
            f"{record.slab_count} slabs) — {len(self._records)} unique files"
        )

    @property
    def records(self) -> List[LearningRecord]:
        return self._records

    @property
    def run_count(self) -> int:
        return len(self._records)

    def _record_weight(self, record: LearningRecord) -> float:
        """Calculate temporal weight for a record (1.0 = recent, 0.5 = old).

        Records older than DECAY_DAYS get halved weight, allowing recent
        runs (with improved detection) to have more influence.
        """
        try:
            ts = datetime.fromisoformat(record.timestamp)
            age_days = (datetime.now() - ts).days
            if age_days > DECAY_DAYS:
                return 0.5
        except (ValueError, TypeError):
            return 0.5
        return 1.0

    # === LEARNED KNOWLEDGE QUERIES ===

    def get_known_beam_layers(self) -> Dict[str, float]:
        """Layers that historically contained beams, with confidence (0-1).

        Returns {layer_name: confidence} where confidence is the weighted
        fraction of unique files where that layer had valid beam candidates.

        Quality gates: beam_count >= 3 AND detection_rate >= 0.02 per record.
        """
        MIN_BEAM_COUNT_THRESHOLD = 3
        MIN_DETECTION_RATE_THRESHOLD = 0.02

        layer_beam_weight: Dict[str, float] = {}
        layer_total_weight: Dict[str, float] = {}

        for r in self._records:
            w = self._record_weight(r)
            seen_layers = set()
            for layer in r.layers:
                name = layer["layer_name"]
                if name not in seen_layers:
                    layer_total_weight[name] = layer_total_weight.get(name, 0) + w
                    seen_layers.add(name)
                beam_count = layer.get("beam_count", 0)
                detection_rate = layer.get("detection_rate", 0.0)
                if (beam_count >= MIN_BEAM_COUNT_THRESHOLD
                        and detection_rate >= MIN_DETECTION_RATE_THRESHOLD):
                    layer_beam_weight[name] = layer_beam_weight.get(name, 0) + w

        result = {}
        for layer, weight in layer_beam_weight.items():
            total = layer_total_weight.get(layer, 1)
            result[layer] = weight / total if total > 0 else 0
        return result

    def purge_low_quality(self) -> int:
        """Remove low-quality layer entries from all records.

        Clears beam_count for layers with detection_rate < 0.02 or beam_count < 3.
        Returns the number of entries cleaned.
        """
        cleaned = 0
        for r in self._records:
            for layer in r.layers:
                beam_count = layer.get("beam_count", 0)
                detection_rate = layer.get("detection_rate", 0.0)
                if beam_count > 0 and (beam_count < 3 or detection_rate < 0.02):
                    layer["beam_count"] = 0
                    cleaned += 1
        if cleaned > 0:
            self.save()
            logger.info(f"Purged {cleaned} low-quality beam layer entries")
        return cleaned

    def deduplicate(self) -> int:
        """Deduplicate records: keep only the latest run per filename.

        Returns the number of records removed.
        """
        before = len(self._records)
        # Group by filename, keep latest (by timestamp)
        by_file: Dict[str, LearningRecord] = {}
        for r in self._records:
            existing = by_file.get(r.filename)
            if existing is None or r.timestamp > existing.timestamp:
                by_file[r.filename] = r

        self._records = list(by_file.values())
        removed = before - len(self._records)
        if removed > 0:
            self.save()
            logger.info(
                f"Deduplicated: {before} → {len(self._records)} records "
                f"({removed} duplicates removed)"
            )
        return removed

    def get_known_pillar_layers(self) -> Dict[str, float]:
        """Layers that historically contained pillars, with confidence."""
        layer_pillar_weight: Dict[str, float] = {}
        layer_total_weight: Dict[str, float] = {}

        for r in self._records:
            w = self._record_weight(r)
            seen_layers = set()
            for layer in r.layers:
                name = layer["layer_name"]
                if name not in seen_layers:
                    layer_total_weight[name] = layer_total_weight.get(name, 0) + w
                    seen_layers.add(name)
                if layer.get("pillar_count", 0) > 0:
                    layer_pillar_weight[name] = layer_pillar_weight.get(name, 0) + w

        result = {}
        for layer, weight in layer_pillar_weight.items():
            total = layer_total_weight.get(layer, 1)
            result[layer] = weight / total if total > 0 else 0
        return result

    def get_common_sections(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """Most common beam section dimensions across unique files.

        Each file contributes its section counts once (no duplicate inflation).
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
        """Average beam confidence score across unique files."""
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

    def get_slab_thickness_history(self) -> Optional[float]:
        """Most commonly found slab thickness value."""
        values: Counter = Counter()
        for r in self._records:
            if r.slab_thickness_found and r.slab_thickness_m is not None:
                values[round(r.slab_thickness_m, 2)] += 1
        if not values:
            return None
        return values.most_common(1)[0][0]

    def get_file_stats(self, filename: str) -> Optional[LearningRecord]:
        """Get the latest learning record for a specific file."""
        for r in reversed(self._records):
            if r.filename == filename:
                return r
        return None

    # === REVISION FEEDBACK ===

    DENSITY_MIN = 0.7
    DENSITY_MAX = 1.5

    def get_shore_density_correction(self) -> float:
        """Average over/under-shoring multiplier from engineer revisions.

        For each record with revision data:
            ratio = (original_total + delta_total) / original_total
        Then weighted by temporal decay and clamped to [DENSITY_MIN, DENSITY_MAX].

        Returns 1.0 if no revision data exists; >1.0 if engineers add shores
        (we are under-shoring), <1.0 if they remove shores (we are over-shoring).
        """
        ratios: List[Tuple[float, float]] = []
        for r in self._records:
            if not r.revision_uploaded:
                continue
            original_total = r.total_shores
            delta_total = r.revision_beam_shore_delta + r.revision_slab_shore_delta
            if original_total <= 0:
                continue
            ratio = (original_total + delta_total) / original_total
            ratios.append((ratio, self._record_weight(r)))

        if not ratios:
            return 1.0

        total_w = sum(w for _, w in ratios)
        if total_w <= 0:
            return 1.0
        weighted = sum(r * w for r, w in ratios) / total_w
        return max(self.DENSITY_MIN, min(self.DENSITY_MAX, weighted))

    def get_validated_layer_map(self) -> Dict[str, str]:
        """Layers seen in revision_added_layers more often than removed_layers.

        These layers had shores placed by a HUMAN engineer, so we treat
        them as confirmed beam/slab carriers at confidence 1.0.

        Returns {layer_name: element_type} where element_type is "beam" or "slab".
        """
        added: Counter = Counter()
        removed: Counter = Counter()
        for r in self._records:
            if not r.revision_uploaded:
                continue
            for layer, count in r.revision_added_layers.items():
                added[layer] += count
            for layer, count in r.revision_removed_layers.items():
                removed[layer] += count

        result: Dict[str, str] = {}
        for layer, n_added in added.items():
            if n_added > removed.get(layer, 0):
                upper = layer.upper()
                if "VIGA" in upper:
                    result[layer] = "beam"
                elif "LAJE" in upper:
                    result[layer] = "slab"
                else:
                    result[layer] = "beam"
        return result

    def update_record_with_revision(self, filename: str, diff: dict) -> None:
        """Find existing record for filename and populate revision_* fields.

        `diff` follows the shape returned by analyze_revision().
        If no record exists for the filename, this is a no-op.
        """
        record = self.get_file_stats(filename)
        if record is None:
            logger.warning(
                f"update_record_with_revision: no learning record for {filename}"
            )
            return

        record.revision_uploaded = True
        record.revision_beam_shore_delta = (
            int(diff.get("beam_added", 0)) - int(diff.get("beam_removed", 0))
        )
        record.revision_slab_shore_delta = (
            int(diff.get("slab_added", 0)) - int(diff.get("slab_removed", 0))
        )
        record.revision_beam_match_rate = (
            float(diff.get("accuracy_beam", 0.0)) / 100.0
        )
        record.revision_slab_match_rate = (
            float(diff.get("accuracy_slab", 0.0)) / 100.0
        )
        beam_moved = int(diff.get("beam_moved", 0))
        record.revision_avg_position_error_m = 0.10 if beam_moved > 0 else 0.0

        added_layers: Dict[str, int] = {}
        removed_layers: Dict[str, int] = {}
        if diff.get("beam_added", 0):
            added_layers["ESCORAS_VIGA"] = int(diff["beam_added"])
        if diff.get("slab_added", 0):
            added_layers["ESCORAS_LAJE"] = int(diff["slab_added"])
        if diff.get("beam_removed", 0):
            removed_layers["ESCORAS_VIGA"] = int(diff["beam_removed"])
        if diff.get("slab_removed", 0):
            removed_layers["ESCORAS_LAJE"] = int(diff["slab_removed"])
        record.revision_added_layers = added_layers
        record.revision_removed_layers = removed_layers

        record.timestamp = datetime.now().isoformat()
        logger.info(
            f"Revision learnings stored for {filename}: "
            f"beam_delta={record.revision_beam_shore_delta}, "
            f"slab_delta={record.revision_slab_shore_delta}"
        )

    def summary(self) -> str:
        """Human-readable summary of accumulated knowledge."""
        if not self._records:
            return "Nenhum dado de aprendizado acumulado."

        unique_files = len(set(r.filename for r in self._records))

        lines = [
            f"=== Escora.AI — Base de Aprendizado (v2) ===",
            f"Arquivos únicos: {unique_files}",
            f"Records armazenados: {len(self._records)}",
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

        # Stats (per unique file, not inflated)
        total_beams = sum(r.beam_count for r in self._records)
        total_pillars = sum(r.pillar_count for r in self._records)
        total_shores = sum(r.total_shores for r in self._records)
        total_slabs = sum(r.slab_count for r in self._records)
        lines.append(f"Totais (por arquivo único):")
        lines.append(f"  Vigas detectadas: {total_beams}")
        lines.append(f"  Pilares detectados: {total_pillars}")
        lines.append(f"  Painéis de laje: {total_slabs}")
        lines.append(f"  Escoras calculadas: {total_shores}")

        pe = self.get_pe_direito_history()
        if pe:
            lines.append(f"  Pé-direito mais comum: {pe:.2f}m")

        default_h = self.get_default_section_height()
        if default_h:
            lines.append(f"  Altura de seção mais comum: {default_h:.2f}m")

        esp = self.get_slab_thickness_history()
        if esp:
            lines.append(f"  Espessura de laje mais comum: {esp:.2f}m")

        # Quality metrics
        valid_runs = sum(1 for r in self._records if r.is_valid)
        lines.append("")
        lines.append(f"Qualidade:")
        lines.append(f"  Runs válidos: {valid_runs}/{len(self._records)}")
        avg_score = self.get_avg_beam_score()
        if avg_score:
            lines.append(f"  Score médio vigas: {avg_score:.0%}")

        return "\n".join(lines)
