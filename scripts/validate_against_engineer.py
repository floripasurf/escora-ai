"""Validation script: strip engineer's shoring, re-calculate, compare.

Workflow:
1. Read engineer's PE (Projeto Executivo) DXF
2. Extract engineer's shoring solution (towers, beams, shores) as ground truth
3. Create a stripped copy with only structural layers (FORMA, VIGAS, PILARES)
4. Run our pipeline on the stripped copy
5. Compare our output vs engineer's ground truth
6. Generate a detailed accuracy report

Usage:
    python3 scripts/validate_against_engineer.py "input/Sergio1/88926-PE-01-Escoramento Lajes -01.dxf"
"""

import sys
import os
import math
import json
import tempfile
import logging
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import ezdxf

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# --- Layer classification ---

# Layers that contain the engineer's shoring solution
SHORING_LAYER_KEYWORDS = [
    "TORRE", "VM130", "VM80", "TA_", "LISTAMAT", "FORCADO", "SAPATA",
    "CRUZETA", "DIAGONAL", "ABRAÇA", "TRIPE", "ESCORAMENTO",
    "ESC310", "ESC360", "ESC450", "SF250", "SF500",
    "PENA_", "MECANER", "Madeira",
]

# Layers to KEEP (structural input). Everything else gets stripped.
# Using a whitelist approach is more reliable for PE files where
# most content IS shoring.
STRUCTURAL_KEEP_LAYERS = {
    "FORMA", "VIGAS", "PILAR_RET", "PILAR_REF", "PILAR_DIM", "PILARES",
    "VIG_REF_VIGAS", "VIG_DIM_VIGAS", "VIG_FACES",
    "FORMATO",  # title block
    "Cotas",  # dimensions
    "EIXO",
}

# Layers that contain structural input (keep these)
STRUCTURAL_LAYER_KEYWORDS = [
    "FORMA", "VIGAS", "PILAR", "LAJE", "EIXO", "FORMATO",
    "VIG_", "Cotas", "HACHURA", "CORTE",
]


@dataclass
class EngineerTower:
    """A tower position extracted from the engineer's DXF."""
    x_cm: float
    y_cm: float
    block_name: str
    layer: str
    width_cm: float = 0
    depth_cm: float = 0
    purpose: str = ""  # "laje" or "viga"

    @property
    def x_m(self) -> float:
        return self.x_cm / 100.0

    @property
    def y_m(self) -> float:
        return self.y_cm / 100.0


@dataclass
class EngineerBeam:
    """A distribution beam from the engineer's DXF."""
    x_cm: float
    y_cm: float
    block_name: str
    layer: str
    model: str = ""
    length_cm: float = 0


@dataclass
class EngineerShore:
    """A telescopic shore from the engineer's DXF."""
    x_cm: float
    y_cm: float
    block_name: str
    layer: str
    model: str = ""


@dataclass
class EngineerSolution:
    """Complete engineer shoring solution extracted from DXF."""
    towers: List[EngineerTower] = field(default_factory=list)
    dist_beams: List[EngineerBeam] = field(default_factory=list)
    shores: List[EngineerShore] = field(default_factory=list)
    bom_text: List[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Result of comparing our solution vs engineer's."""
    engineer_tower_count: int = 0
    our_tower_count: int = 0
    our_shore_count: int = 0
    engineer_shore_count: int = 0
    engineer_beam_count: int = 0
    matched_positions: int = 0
    unmatched_engineer: int = 0
    unmatched_ours: int = 0
    avg_position_error_m: float = 0.0
    max_position_error_m: float = 0.0
    warnings: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)


def is_shoring_layer(layer_name: str) -> bool:
    """Check if a layer contains shoring solution entities."""
    ln = layer_name.lower()
    return any(kw.lower() in ln for kw in SHORING_LAYER_KEYWORDS)


def parse_tower_block_name(block_name: str) -> Tuple[float, float, str]:
    """Parse tower block name to extract dimensions and purpose.

    Patterns:
        100x155lj  → width=100, depth=155, purpose=laje
        154x205VG  → width=154, depth=205, purpose=viga
        1001551    → width=100, depth=155, purpose=laje (compact format)
        1541001    → width=154, depth=100, purpose=laje (compact format)
    """
    import re

    # Standard format: NNNxNNN{lj|vg|VG}
    m = re.match(r"(\d+)x(\d+)(lj|vg|VG)", block_name, re.IGNORECASE)
    if m:
        w, d = float(m.group(1)), float(m.group(2))
        purpose = "laje" if m.group(3).lower() == "lj" else "viga"
        return w, d, purpose

    # Compact format: WWWDDDN where N=1(laje) or 0(viga)
    m = re.match(r"(\d{3})(\d{3})([01])", block_name)
    if m:
        w, d = float(m.group(1)), float(m.group(2))
        purpose = "laje" if m.group(3) == "1" else "viga"
        return w, d, purpose

    return 0, 0, "unknown"


def extract_engineer_solution(filepath: str) -> EngineerSolution:
    """Extract the engineer's shoring solution from a PE DXF file."""
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    sol = EngineerSolution()

    for entity in msp:
        layer = entity.dxf.layer
        etype = entity.dxftype()

        # Towers
        if "TORRE" in layer.upper() and etype == "INSERT":
            block_name = entity.dxf.name
            x, y = entity.dxf.insert.x, entity.dxf.insert.y
            w, d, purpose = parse_tower_block_name(block_name)

            # Skip accessories and detail view blocks
            if block_name.lower() in ("esticador", "grampo cabo", "grampo cabo planta", "cons710"):
                continue

            sol.towers.append(EngineerTower(
                x_cm=x, y_cm=y, block_name=block_name, layer=layer,
                width_cm=w, depth_cm=d, purpose=purpose,
            ))

        # Distribution beams (VM130, VM80)
        elif ("VM130" in layer.upper() or "VM80" in layer.upper()) and etype == "INSERT":
            block_name = entity.dxf.name
            x, y = entity.dxf.insert.x, entity.dxf.insert.y
            # Extract model and length from block name like VM130-360
            model = block_name.split("-")[0] if "-" in block_name else block_name
            length = 0
            if "-" in block_name:
                try:
                    length = float(block_name.split("-")[1])
                except (ValueError, IndexError):
                    pass
            sol.dist_beams.append(EngineerBeam(
                x_cm=x, y_cm=y, block_name=block_name, layer=layer,
                model=model, length_cm=length,
            ))

        # Telescopic shores (TA)
        elif "TA_" in layer.upper() and etype == "INSERT":
            block_name = entity.dxf.name
            x, y = entity.dxf.insert.x, entity.dxf.insert.y
            if "TUBO" not in block_name.upper() and "SUPORTE" not in block_name.upper():
                sol.shores.append(EngineerShore(
                    x_cm=x, y_cm=y, block_name=block_name, layer=layer,
                    model=block_name,
                ))

        # BOM text
        elif "LISTAMAT" in layer.upper() and etype in ("TEXT", "MTEXT"):
            text = entity.dxf.text if etype == "TEXT" else entity.text
            if text and text.strip():
                sol.bom_text.append(text.strip())

    return sol


def should_keep_layer(layer_name: str) -> bool:
    """Whitelist check: only keep structural layers."""
    # Exact match
    if layer_name in STRUCTURAL_KEEP_LAYERS:
        return True
    # Prefix match for pillar/beam sublayers
    ln = layer_name.upper()
    if any(ln.startswith(k.upper()) for k in ["PILAR", "VIG_", "FORMA", "VIGAS"]):
        return True
    return False


def create_stripped_dxf(input_path: str, output_path: str) -> Tuple[int, int]:
    """Create a copy of the DXF keeping ONLY structural layers.

    Uses whitelist approach — PE files have mostly shoring content,
    so it's safer to keep only known structural layers.

    Returns (kept_count, removed_count).
    """
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()

    to_delete = []
    kept = 0
    for entity in msp:
        if should_keep_layer(entity.dxf.layer):
            kept += 1
        else:
            to_delete.append(entity)

    for entity in to_delete:
        msp.delete_entity(entity)

    doc.saveas(output_path)
    return kept, len(to_delete)


def run_our_pipeline(stripped_dxf_path: str, scale_override: Optional[float] = None):
    """Run our shoring pipeline on the stripped DXF."""
    from src.pipeline.runner import run_pipeline
    return run_pipeline(stripped_dxf_path, scale_override=scale_override)


def compare_solutions(
    engineer: EngineerSolution,
    our_result,
    match_radius_m: float = 0.50,
) -> ComparisonResult:
    """Compare our pipeline output against engineer's ground truth.

    match_radius_m: maximum distance (meters) to consider a position match.
    """
    result = ComparisonResult()

    # Filter engineer towers to plan-view only (exclude detail/section view blocks)
    plan_towers = [
        t for t in engineer.towers
        if t.width_cm > 0 and t.depth_cm > 0
    ]
    result.engineer_tower_count = len(plan_towers)
    result.engineer_shore_count = len(engineer.shores)
    result.engineer_beam_count = len(engineer.dist_beams)

    # Count our shores
    our_positions = []
    if our_result and our_result.calculation:
        calc = our_result.calculation
        for br in calc.beam_results:
            for s in br.shores:
                our_positions.append((s.x, s.y, "beam"))
        for sr in calc.slab_results:
            for s in sr.shores:
                our_positions.append((s.x, s.y, "slab"))

    result.our_shore_count = len(our_positions)

    # --- Position matching ---
    # Convert engineer positions to meters for comparison
    eng_positions_m = [(t.x_m, t.y_m, t.purpose) for t in plan_towers]
    # Also add telescopic shore positions
    eng_positions_m.extend([(s.x_cm / 100.0, s.y_cm / 100.0, "shore") for s in engineer.shores])

    total_eng = len(eng_positions_m)

    if not our_positions or not eng_positions_m:
        result.unmatched_engineer = total_eng
        result.unmatched_ours = len(our_positions)
        result.warnings.append("Cannot compare — one side has no positions")
        return result

    # Greedy nearest-neighbor matching
    matched_eng = set()
    matched_ours = set()
    distances = []

    for oi, (ox, oy, otype) in enumerate(our_positions):
        best_dist = float("inf")
        best_ei = -1
        for ei, (ex, ey, epurpose) in enumerate(eng_positions_m):
            if ei in matched_eng:
                continue
            d = math.hypot(ox - ex, oy - ey)
            if d < best_dist:
                best_dist = d
                best_ei = ei

        if best_ei >= 0 and best_dist <= match_radius_m:
            matched_eng.add(best_ei)
            matched_ours.add(oi)
            distances.append(best_dist)
            result.details.append(
                f"MATCH: our ({ox:.2f}, {oy:.2f}) ↔ eng ({eng_positions_m[best_ei][0]:.2f}, "
                f"{eng_positions_m[best_ei][1]:.2f}) — Δ={best_dist:.3f}m"
            )

    result.matched_positions = len(distances)
    result.unmatched_engineer = total_eng - len(matched_eng)
    result.unmatched_ours = len(our_positions) - len(matched_ours)

    if distances:
        result.avg_position_error_m = sum(distances) / len(distances)
        result.max_position_error_m = max(distances)

    # Report unmatched engineer positions
    for ei, (ex, ey, epurpose) in enumerate(eng_positions_m):
        if ei not in matched_eng:
            result.details.append(
                f"MISSING: engineer has {epurpose} at ({ex:.2f}, {ey:.2f}) — we don't"
            )

    # Report unmatched our positions
    for oi, (ox, oy, otype) in enumerate(our_positions):
        if oi not in matched_ours:
            result.details.append(
                f"EXTRA: we placed {otype} shore at ({ox:.2f}, {oy:.2f}) — engineer doesn't"
            )

    return result


def print_report(
    filepath: str,
    engineer: EngineerSolution,
    comparison: ComparisonResult,
    our_result,
):
    """Print a formatted validation report."""
    name = os.path.basename(filepath)

    print(f"\n{'='*70}")
    print(f"  VALIDATION REPORT: {name}")
    print(f"{'='*70}")

    print(f"\n--- Engineer's Solution ---")
    print(f"  Towers:             {comparison.engineer_tower_count}")
    print(f"  Telescopic shores:  {comparison.engineer_shore_count}")
    print(f"  Distribution beams: {comparison.engineer_beam_count}")

    # Tower type breakdown
    tower_types = Counter(
        f"{t.width_cm:.0f}x{t.depth_cm:.0f} ({t.purpose})"
        for t in engineer.towers if t.width_cm > 0
    )
    if tower_types:
        print(f"  Tower types:")
        for ttype, count in tower_types.most_common():
            print(f"    {ttype}: {count}")

    # Beam model breakdown
    beam_models = Counter(b.block_name for b in engineer.dist_beams)
    if beam_models:
        print(f"  Beam models:")
        for model, count in beam_models.most_common():
            print(f"    {model}: {count}")

    print(f"\n--- Our Pipeline Result ---")
    if our_result and our_result.calculation:
        calc = our_result.calculation
        print(f"  Total shores:       {calc.total_shores}")
        print(f"  Beam results:       {len(calc.beam_results)}")
        print(f"  Slab results:       {len(calc.slab_results)}")
        print(f"  Construction type:  {our_result.construction_type}")
        print(f"  Slab type:          {our_result.slab_type}")
        print(f"  Scale:              {our_result.scale}")
    else:
        print(f"  (calculation failed or no elements)")

    print(f"\n--- Comparison ---")
    total_eng = comparison.engineer_tower_count + comparison.engineer_shore_count
    print(f"  Engineer total supports:  {total_eng}")
    print(f"  Our total supports:       {comparison.our_shore_count}")
    print(f"  Matched positions:        {comparison.matched_positions}")
    print(f"  Unmatched (engineer has):  {comparison.unmatched_engineer}")
    print(f"  Unmatched (we have extra): {comparison.unmatched_ours}")

    if comparison.matched_positions > 0:
        accuracy = comparison.matched_positions / max(total_eng, 1) * 100
        print(f"  Position accuracy:        {accuracy:.1f}%")
        print(f"  Avg position error:       {comparison.avg_position_error_m:.3f}m")
        print(f"  Max position error:       {comparison.max_position_error_m:.3f}m")
    else:
        print(f"  Position accuracy:        0% (no matches)")

    # Warnings from pipeline
    if our_result and our_result.warnings:
        print(f"\n--- Pipeline Warnings ({len(our_result.warnings)}) ---")
        for w in our_result.warnings[:20]:
            print(f"  ⚠ {w}")
        if len(our_result.warnings) > 20:
            print(f"  ... and {len(our_result.warnings) - 20} more")

    # Show first few comparison details
    if comparison.details:
        print(f"\n--- Position Details (first 30) ---")
        for d in comparison.details[:30]:
            print(f"  {d}")
        if len(comparison.details) > 30:
            print(f"  ... and {len(comparison.details) - 30} more")

    print(f"\n{'='*70}")


def main():
    if len(sys.argv) < 2:
        # Default: run on all Sergio1 files
        sergio_dir = Path(__file__).parent.parent / "input" / "Sergio1"
        files = sorted(sergio_dir.glob("*.dxf"))
        if not files:
            print("No Sergio1 DXF files found. Provide a path as argument.")
            sys.exit(1)
    else:
        files = [Path(sys.argv[1])]

    for filepath in files:
        filepath_str = str(filepath)
        logger.info(f"Processing: {filepath.name}")

        # Step 1: Extract engineer's solution
        logger.info("Extracting engineer's shoring solution...")
        engineer = extract_engineer_solution(filepath_str)
        logger.info(
            f"  Found: {len(engineer.towers)} towers, "
            f"{len(engineer.dist_beams)} dist beams, "
            f"{len(engineer.shores)} telescopic shores"
        )

        # Step 2: Create stripped copy
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            stripped_path = tmp.name

        try:
            kept, removed = create_stripped_dxf(filepath_str, stripped_path)
            logger.info(f"  Kept {kept}, stripped {removed} entities → {stripped_path}")

            # Detect if coordinates are in cm (PE files from Sergio1 are in cm)
            # If coordinate range > 500, assume cm → use scale 0.01
            doc_check = ezdxf.readfile(stripped_path)
            msp_check = doc_check.modelspace()
            xs, ys = [], []
            for e in msp_check:
                if e.dxftype() == "LINE":
                    xs.extend([e.dxf.start.x, e.dxf.end.x])
                    ys.extend([e.dxf.start.y, e.dxf.end.y])
            coord_range = max(max(xs) - min(xs), max(ys) - min(ys)) if xs and ys else 0
            scale_override = 0.01 if coord_range > 500 else None
            if scale_override:
                logger.info(f"  Coordinate range {coord_range:.0f} — assuming cm units (scale=0.01)")

            # Step 3: Run our pipeline
            logger.info("Running our pipeline on stripped DXF...")
            try:
                our_result = run_our_pipeline(stripped_path, scale_override=scale_override)
            except Exception as e:
                logger.error(f"  Pipeline failed: {e}")
                import traceback
                traceback.print_exc()
                our_result = None

            # Step 4: Compare
            comparison = compare_solutions(engineer, our_result)

            # Step 5: Report
            print_report(filepath_str, engineer, comparison, our_result)

        finally:
            # Clean up temp file
            if os.path.exists(stripped_path):
                os.unlink(stripped_path)


if __name__ == "__main__":
    main()
