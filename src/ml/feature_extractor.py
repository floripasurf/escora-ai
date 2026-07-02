"""Feature extraction from structural geometry for ML models.

Converts raw structural elements (beams, pillars) and engineer decisions
(towers, shores) into feature vectors for supervised learning.

Features per structural beam:
- Geometric: length, midpoint coords, orientation angle
- Context: distance to nearest pillar, number of nearby pillars
- Load proxy: estimated tributary area, nearby beam density
- Span: free span between supports

Labels (what the engineer decided):
- support_type: 'tower' or 'telescopic' or 'none'
- tower_size: width x depth (cm) if tower
- shore_count: number of shores along this beam
- spacing: average spacing between supports
- dist_beam_model: VM130 or VM80
"""

import json
import math
import logging
from typing import List, Tuple
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrainingExample:
    """One training example = one structural beam + engineer's decision."""
    # Features (input)
    beam_length_m: float
    beam_cx_m: float  # midpoint X
    beam_cy_m: float  # midpoint Y
    beam_angle_deg: float  # 0=horizontal, 90=vertical
    nearest_pillar_dist_m: float
    pillar_count_3m: int  # pillars within 3m radius
    nearby_beam_count: int  # beams within 2m
    nearby_beam_avg_length_m: float
    is_perimeter: bool  # near the bounding box edge

    # Labels (engineer's decision)
    support_type: str  # 'tower', 'telescopic', 'none'
    tower_width_cm: float = 0
    tower_depth_cm: float = 0
    shore_count: int = 0
    avg_spacing_m: float = 0
    dist_beam_model: str = ""  # 'VM130', 'VM80', ''

    # Metadata
    file_name: str = ""


def _dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def _midpoint(x1, y1, x2, y2):
    return (x1 + x2) / 2, (y1 + y2) / 2


def _angle_deg(x1, y1, x2, y2):
    return math.degrees(math.atan2(abs(y2 - y1), abs(x2 - x1)))


def extract_training_data(data_path: str) -> List[TrainingExample]:
    """Extract training examples from the Sergio1 extracted JSON.

    For each structural beam, finds the nearest engineer support (tower/shore)
    and creates a labeled training example.
    """
    with open(data_path, "r", encoding="utf-8") as f:
        all_files = json.load(f)

    examples = []

    for file_data in all_files:
        file_name = file_data["file"]
        beams = file_data["beams"]
        pillars = file_data["pillars"]
        towers = file_data["towers"]
        shores = file_data["shores"]
        dist_beams = file_data["dist_beams"]

        if not beams:
            continue

        # Compute bounding box of structural elements
        all_x = [b["x1"] for b in beams] + [b["x2"] for b in beams]
        all_y = [b["y1"] for b in beams] + [b["y2"] for b in beams]
        bbox_min_x, bbox_max_x = min(all_x), max(all_x)
        bbox_min_y, bbox_max_y = min(all_y), max(all_y)
        bbox_margin = 200  # cm — within 2m of edge = perimeter

        # Pillar positions
        pillar_pts = [(p["cx"], p["cy"]) for p in pillars]

        # Tower positions with metadata
        tower_pts = [(t["x"], t["y"], t["width_cm"], t["depth_cm"], t["purpose"]) for t in towers]

        # Shore positions
        shore_pts = [(s["x"], s["y"], s["model"], s["purpose"]) for s in shores]

        # Distribution beam positions
        db_pts = [(d["x"], d["y"], d["model"]) for d in dist_beams]

        # Beam midpoints for neighbor counting
        beam_mids = []
        for b in beams:
            mx, my = _midpoint(b["x1"], b["y1"], b["x2"], b["y2"])
            beam_mids.append((mx, my, b["length_cm"]))

        for bi, beam in enumerate(beams):
            length_cm = beam["length_cm"]
            if length_cm < 80:  # Skip very short segments
                continue

            mx, my = beam_mids[bi][0], beam_mids[bi][1]
            angle = _angle_deg(beam["x1"], beam["y1"], beam["x2"], beam["y2"])

            # Nearest pillar
            nearest_pillar = float("inf")
            pillar_count_3m = 0
            for px, py in pillar_pts:
                d = _dist(mx, my, px, py)
                nearest_pillar = min(nearest_pillar, d)
                if d <= 300:  # 3m in cm
                    pillar_count_3m += 1
            if nearest_pillar == float("inf"):
                nearest_pillar = 9999

            # Nearby beams
            nearby_count = 0
            nearby_lengths = []
            for bj, (bmx, bmy, blen) in enumerate(beam_mids):
                if bi == bj:
                    continue
                if _dist(mx, my, bmx, bmy) <= 200:  # 2m in cm
                    nearby_count += 1
                    nearby_lengths.append(blen)
            avg_nearby_len = sum(nearby_lengths) / len(nearby_lengths) if nearby_lengths else 0

            # Is perimeter beam?
            is_perimeter = (
                mx - bbox_min_x < bbox_margin or bbox_max_x - mx < bbox_margin or
                my - bbox_min_y < bbox_margin or bbox_max_y - my < bbox_margin
            )

            # --- Find engineer's decision for this beam ---
            # Find nearest tower
            nearest_tower_dist = float("inf")
            nearest_tower = None
            for tx, ty, tw, td, tp in tower_pts:
                d = _dist(mx, my, tx, ty)
                if d < nearest_tower_dist:
                    nearest_tower_dist = d
                    nearest_tower = (tw, td, tp)

            # Find nearest shore
            nearest_shore_dist = float("inf")
            nearest_shore_model = ""
            for sx, sy, sm, sp in shore_pts:
                d = _dist(mx, my, sx, sy)
                if d < nearest_shore_dist:
                    nearest_shore_dist = d
                    nearest_shore_model = sm

            # Find nearest distribution beam
            nearest_db_dist = float("inf")
            nearest_db_model = ""
            for dx, dy, dm in db_pts:
                d = _dist(mx, my, dx, dy)
                if d < nearest_db_dist:
                    nearest_db_dist = d
                    nearest_db_model = dm

            # Decide label: what did the engineer use here?
            # Threshold: if a support is within 300cm (3m) of beam midpoint, it's "for" this beam
            support_radius = 300  # cm

            if nearest_tower_dist <= support_radius and nearest_tower:
                support_type = "tower"
                tw, td = nearest_tower[0], nearest_tower[1]
            elif nearest_shore_dist <= support_radius:
                support_type = "telescopic"
                tw, td = 0, 0
            else:
                support_type = "none"
                tw, td = 0, 0

            # Count shores near this beam for spacing estimation
            beam_shores = []
            for sx, sy, sm, sp in shore_pts:
                # Check if shore is near this beam's axis
                d_to_mid = _dist(mx, my, sx, sy)
                if d_to_mid <= length_cm * 0.6:  # within beam extent
                    beam_shores.append((sx, sy))

            shore_count = len(beam_shores)
            avg_spacing = length_cm / max(shore_count + 1, 2) if shore_count > 0 else 0

            # Distribution beam model
            db_model = ""
            if nearest_db_dist <= support_radius:
                if "VM130" in nearest_db_model:
                    db_model = "VM130"
                elif "VM80" in nearest_db_model:
                    db_model = "VM80"

            examples.append(TrainingExample(
                beam_length_m=round(length_cm / 100, 2),
                beam_cx_m=round(mx / 100, 2),
                beam_cy_m=round(my / 100, 2),
                beam_angle_deg=round(angle, 1),
                nearest_pillar_dist_m=round(nearest_pillar / 100, 2),
                pillar_count_3m=pillar_count_3m,
                nearby_beam_count=nearby_count,
                nearby_beam_avg_length_m=round(avg_nearby_len / 100, 2),
                is_perimeter=is_perimeter,
                support_type=support_type,
                tower_width_cm=tw,
                tower_depth_cm=td,
                shore_count=shore_count,
                avg_spacing_m=round(avg_spacing / 100, 2),
                dist_beam_model=db_model,
                file_name=file_name,
            ))

    logger.info(f"Extracted {len(examples)} training examples from {len(all_files)} files")
    return examples


def examples_to_arrays(examples: List[TrainingExample]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Convert training examples to numpy arrays for sklearn.

    Returns:
        X: feature matrix (n_samples, n_features)
        y: label array (n_samples,) — support type encoded as int
        feature_names: list of feature column names
    """
    feature_names = [
        "beam_length_m",
        "beam_angle_deg",
        "nearest_pillar_dist_m",
        "pillar_count_3m",
        "nearby_beam_count",
        "nearby_beam_avg_length_m",
        "is_perimeter",
    ]

    X = np.array([
        [
            e.beam_length_m,
            e.beam_angle_deg,
            e.nearest_pillar_dist_m,
            e.pillar_count_3m,
            e.nearby_beam_count,
            e.nearby_beam_avg_length_m,
            1.0 if e.is_perimeter else 0.0,
        ]
        for e in examples
    ])

    # Encode labels
    label_map = {"none": 0, "telescopic": 1, "tower": 2}
    y = np.array([label_map.get(e.support_type, 0) for e in examples])

    return X, y, feature_names
