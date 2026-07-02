"""Stage 6: Learning — extract knowledge from a completed pipeline run.

After each DXF is processed, this stage records what happened:
- Which layers contained structural elements
- What section dimensions were found
- Detection confidence distributions
- Metadata extraction success

This data accumulates in the LearningStore and is used to improve
future runs (layer prioritization, default sections, threshold tuning).

Additionally, the source DXF and a results snapshot are preserved in
data/learning/files/ so a training dataset grows organically.
"""

import hashlib
import json
import logging
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.pipeline_models import PipelineResult, ElementType
from src.pipeline.learning_store import LearningRecord, LearningStore
from src.parser.segment_classifier import find_beam_candidates, find_pillar_candidates

logger = logging.getLogger(__name__)


def extract_learning(
    result: PipelineResult,
    level_segments: Optional[list] = None,
) -> LearningRecord:
    """Extract a learning record from a completed pipeline run.

    Args:
        result: The PipelineResult from run_pipeline.
        level_segments: Original LevelSegments (for layer-level stats).

    Returns:
        LearningRecord ready to be saved.
    """
    all_elements = []
    for level in result.levels:
        all_elements.extend(level.elements)

    beams = [e for e in all_elements if e.element_type == ElementType.BEAM]
    pillars = [e for e in all_elements if e.element_type == ElementType.PILLAR]

    # Section frequency
    section_freq: Counter = Counter()
    for b in beams:
        if b.section_width_m is not None and b.section_height_m is not None:
            w_cm = round(b.section_width_m * 100)
            h_cm = round(b.section_height_m * 100)
            section_freq[f"{w_cm}x{h_cm}"] += 1

    # Score averages
    beam_scores = [b.score_final for b in beams if b.score_final > 0]
    pillar_scores = [p.score_final for p in pillars if p.score_final > 0]

    # Layer analysis
    layers = []
    if level_segments:
        from collections import defaultdict
        for seg in level_segments:
            segs_by_layer = defaultdict(list)
            for s in seg.segments:
                if s.type == "H":
                    segs_by_layer[s.layer].append(
                        {"type": "H", "y": s.y, "x_min": s.x_min, "x_max": s.x_max}
                    )
                else:
                    segs_by_layer[s.layer].append(
                        {"type": "V", "x": s.x, "y_min": s.y_min, "y_max": s.y_max}
                    )

            rects_by_layer = defaultdict(list)
            for r in seg.rects:
                rects_by_layer[r.layer].append({
                    "cx": r.cx, "cy": r.cy,
                    "width": r.width, "height": r.height, "area": r.area,
                })

            all_layers = set(list(segs_by_layer.keys()) + list(rects_by_layer.keys()))
            for layer_name in all_layers:
                seg_dicts = segs_by_layer.get(layer_name, [])
                rect_dicts = rects_by_layer.get(layer_name, [])

                beam_candidates = find_beam_candidates(seg_dicts) if seg_dicts else []
                pillar_candidates = find_pillar_candidates(rect_dicts) if rect_dicts else []

                if beam_candidates or pillar_candidates:
                    layers.append({
                        "layer_name": layer_name,
                        "beam_count": len(beam_candidates),
                        "pillar_count": len(pillar_candidates),
                        "segment_count": len(seg_dicts),
                        "rect_count": len(rect_dicts),
                        "detection_rate": (
                            len(beam_candidates) / max(len(seg_dicts), 1)
                            if beam_candidates else 0
                        ),
                    })

    # Layer → element type map
    layer_element_map = {}
    for layer in layers:
        if layer["beam_count"] > layer["pillar_count"]:
            layer_element_map[layer["layer_name"]] = "BEAM"
        elif layer["pillar_count"] > 0:
            layer_element_map[layer["layer_name"]] = "PILLAR"

    # Metadata
    pe_direito = result.levels[0].pe_direito_m if result.levels else None
    pe_direito_found = not any("pe-direito" in w.lower() or "pé-direito" in w.lower()
                               for w in result.warnings
                               if "padrão" in w.lower() or "nao encontrado" in w.lower())

    calc = result.calculation
    error_count = 0
    warning_count = len(result.warnings)
    if calc:
        error_count = len(calc.validation_errors)

    return LearningRecord(
        filename=result.filename,
        timestamp=datetime.now().isoformat(),
        scale=result.scale,
        beam_count=len(beams),
        pillar_count=len(pillars),
        slab_count=len(calc.slab_results) if calc else 0,
        beams_with_name=sum(1 for b in beams if b.name),
        beams_with_section=sum(1 for b in beams if b.section_height_m),
        beams_estimated_height=sum(
            1 for w in result.warnings if "estimada" in w
        ),
        beam_score_avg=sum(beam_scores) / len(beam_scores) if beam_scores else 0,
        pillar_score_avg=sum(pillar_scores) / len(pillar_scores) if pillar_scores else 0,
        layers=layers,
        section_freq=dict(section_freq),
        layer_element_map=layer_element_map,
        pe_direito_m=pe_direito,
        pe_direito_found=pe_direito_found,
        slab_thickness_m=calc.slab_results[0].thickness_m if calc and calc.slab_results else None,
        slab_thickness_found=any("espessura" not in w.lower() for w in result.warnings),
        total_shores=calc.total_shores if calc else 0,
        total_load_kn=calc.total_load_kn if calc else 0,
        is_valid=calc.is_valid if calc else False,
        warning_count=warning_count,
        error_count=error_count,
    )


def _learning_files_dir() -> Path:
    """Directory where input DXFs and result snapshots are preserved."""
    return Path(os.environ.get("ESCORA_DATA_DIR", "./data")) / "learning" / "files"


def _preserve_source_file(source_path: str, result: PipelineResult) -> None:
    """Copy input DXF and save a results JSON snapshot for future training.

    Files are stored as:
        data/learning/files/{stem}_{hash8}/input.dxf
        data/learning/files/{stem}_{hash8}/results.json

    The hash is derived from file content so re-runs of the same file
    overwrite the previous snapshot (dedup by content, not name).
    """
    src = Path(source_path)
    if not src.exists():
        return

    # Content hash for dedup (first 8 hex chars)
    h = hashlib.md5()
    with open(src, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    content_hash = h.hexdigest()[:8]

    stem = src.stem
    dest_dir = _learning_files_dir() / f"{stem}_{content_hash}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy input DXF (only if not already there)
    dest_dxf = dest_dir / f"input{src.suffix}"
    if not dest_dxf.exists():
        shutil.copy2(str(src), str(dest_dxf))

    # Save results snapshot
    calc = result.calculation
    snapshot = {
        "filename": result.filename,
        "timestamp": datetime.now().isoformat(),
        "scale": result.scale,
        "construction_type": result.construction_type,
        "slab_type": result.slab_type,
        "warnings": result.warnings[:50],
        "beam_count": sum(
            1 for lvl in result.levels for e in lvl.elements
            if e.element_type == ElementType.BEAM
        ),
        "pillar_count": sum(
            1 for lvl in result.levels for e in lvl.elements
            if e.element_type == ElementType.PILLAR
        ),
    }
    if calc:
        snapshot["total_shores"] = getattr(calc, "total_shores", 0)
        snapshot["total_load_kn"] = getattr(calc, "total_load_kn", 0.0)
        snapshot["is_valid"] = getattr(calc, "is_valid", False)
        snapshot["beam_results_count"] = len(getattr(calc, "beam_results", []))
        snapshot["slab_results_count"] = len(getattr(calc, "slab_results", []))
        # Save per-beam summary
        beam_summaries = []
        for br in getattr(calc, "beam_results", []):
            beam_summaries.append({
                "name": getattr(br, "name", None) or getattr(getattr(br, "beam", None), "name", None),
                "shore_count": getattr(br, "shore_count", 0),
                "spacing_m": getattr(br, "spacing_m", 0),
            })
        snapshot["beam_results"] = beam_summaries[:200]
        # Save per-slab summary
        slab_summaries = []
        for sr in getattr(calc, "slab_results", []):
            slab_summaries.append({
                "area_m2": getattr(sr, "area_m2", 0),
                "thickness_m": getattr(sr, "thickness_m", 0),
                "shore_count": getattr(sr, "shore_count", 0),
            })
        snapshot["slab_results"] = slab_summaries[:200]

    (dest_dir / "results.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False)
    )
    logger.info(f"Preserved learning files: {dest_dir}")


def learn_and_save(
    result: PipelineResult,
    level_segments: Optional[list] = None,
    store: Optional[LearningStore] = None,
    source_dxf_path: Optional[str] = None,
) -> LearningRecord:
    """Extract learning from a pipeline run and save it.

    Args:
        result: Completed PipelineResult.
        level_segments: Original level segments for layer analysis.
        store: LearningStore instance (creates default if None).
        source_dxf_path: Path to the original input DXF (preserved for training).

    Returns:
        The saved LearningRecord.
    """
    if store is None:
        store = LearningStore()

    record = extract_learning(result, level_segments)
    store.add(record)

    # Preserve source file + results for future training
    if source_dxf_path:
        try:
            _preserve_source_file(source_dxf_path, result)
        except Exception as e:
            logger.warning(f"Failed to preserve learning files (non-fatal): {e}")

    return record
