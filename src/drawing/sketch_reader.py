"""Sketch/image reader — converts hand-drawn floor plans to BuildingModel.

Processes a photo or scan of a floor plan sketch and extracts:
- Wall lines (using Hough line detection)
- Room boundaries (from enclosed areas)
- Approximate dimensions (from detected text or scale reference)

The output is a BuildingModel that can be refined and used to generate
professional DXF drawings.

Usage:
    from src.drawing.sketch_reader import read_sketch

    model = read_sketch("sketch.jpg", scale_reference_m=7.0)
    sheet = TechnicalSheet("A2", scale="1:50")
    sheet.draw_plan(model, auto_dim=True)
    sheet.save("from_sketch.dxf")

Pipeline:
    1. Preprocessing: grayscale, adaptive threshold, noise removal
    2. Line detection: probabilistic Hough transform
    3. Line merging: cluster near-collinear segments
    4. Wall classification: filter by length, angle, parallelism
    5. Junction detection: find wall intersections
    6. Coordinate snapping: align to grid
    7. BuildingModel construction: create walls from cleaned lines
"""

import math
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

Point2D = Tuple[float, float]


@dataclass
class DetectedLine:
    """A line segment detected from the image."""
    x1: float
    y1: float
    x2: float
    y2: float
    strength: float = 1.0  # Detection confidence

    @property
    def length(self) -> float:
        return math.sqrt((self.x2 - self.x1)**2 + (self.y2 - self.y1)**2)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.y2 - self.y1, self.x2 - self.x1))

    @property
    def is_horizontal(self) -> bool:
        return abs(self.angle_deg) < 15 or abs(self.angle_deg) > 165

    @property
    def is_vertical(self) -> bool:
        return 75 < abs(self.angle_deg) < 105

    @property
    def is_cardinal(self) -> bool:
        return self.is_horizontal or self.is_vertical

    @property
    def midpoint(self) -> Point2D:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class SketchConfig:
    """Configuration for sketch reading."""
    min_line_length_px: int = 50      # Minimum line length in pixels
    max_line_gap_px: int = 15         # Maximum gap to merge collinear lines
    hough_threshold: int = 80         # Hough accumulator threshold
    merge_angle_tol_deg: float = 10   # Angle tolerance for merging lines
    merge_dist_tol_px: float = 20     # Distance tolerance for merging lines
    snap_grid_px: float = 10          # Grid snapping in pixels
    wall_thickness_m: float = 0.15    # Assumed wall thickness
    default_height_m: float = 2.80    # Default wall height


def _preprocess(image: np.ndarray) -> np.ndarray:
    """Preprocess image for line detection."""
    import cv2

    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Increase contrast
    gray = cv2.equalizeHist(gray)

    # Adaptive threshold (handles uneven lighting from phone photos)
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15, C=10,
    )

    # Morphological operations to clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    return binary


def _detect_lines(
    binary: np.ndarray,
    config: SketchConfig,
) -> List[DetectedLine]:
    """Detect line segments using probabilistic Hough transform."""
    import cv2

    lines = cv2.HoughLinesP(
        binary,
        rho=1,
        theta=np.pi / 180,
        threshold=config.hough_threshold,
        minLineLength=config.min_line_length_px,
        maxLineGap=config.max_line_gap_px,
    )

    if lines is None:
        return []

    detected = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        detected.append(DetectedLine(
            x1=float(x1), y1=float(y1),
            x2=float(x2), y2=float(y2),
        ))

    logger.info(f"Detected {len(detected)} raw line segments")
    return detected


def _merge_collinear(
    lines: List[DetectedLine],
    config: SketchConfig,
) -> List[DetectedLine]:
    """Merge near-collinear line segments into single lines."""
    if not lines:
        return []

    merged = []
    used = set()

    for i, line_a in enumerate(lines):
        if i in used:
            continue

        # Collect all lines that are collinear with line_a
        group = [line_a]
        used.add(i)

        for j, line_b in enumerate(lines):
            if j in used:
                continue

            # Check angle similarity
            angle_diff = abs(line_a.angle_deg - line_b.angle_deg)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            if angle_diff > config.merge_angle_tol_deg and \
               abs(angle_diff - 180) > config.merge_angle_tol_deg:
                continue

            # Check distance between midpoints projected onto perpendicular
            mx_a, my_a = line_a.midpoint
            mx_b, my_b = line_b.midpoint

            if line_a.is_horizontal:
                dist = abs(my_a - my_b)
            elif line_a.is_vertical:
                dist = abs(mx_a - mx_b)
            else:
                # General case: perpendicular distance
                angle_rad = math.radians(line_a.angle_deg)
                nx, ny = -math.sin(angle_rad), math.cos(angle_rad)
                dist = abs((mx_b - mx_a) * nx + (my_b - my_a) * ny)

            if dist < config.merge_dist_tol_px:
                group.append(line_b)
                used.add(j)

        # Merge group into a single line (use extreme endpoints)
        all_pts = []
        for ln in group:
            all_pts.append((ln.x1, ln.y1))
            all_pts.append((ln.x2, ln.y2))

        if line_a.is_horizontal:
            # Sort by X, take extremes
            all_pts.sort(key=lambda p: p[0])
            avg_y = sum(p[1] for p in all_pts) / len(all_pts)
            merged.append(DetectedLine(
                all_pts[0][0], avg_y,
                all_pts[-1][0], avg_y,
                strength=len(group),
            ))
        elif line_a.is_vertical:
            all_pts.sort(key=lambda p: p[1])
            avg_x = sum(p[0] for p in all_pts) / len(all_pts)
            merged.append(DetectedLine(
                avg_x, all_pts[0][1],
                avg_x, all_pts[-1][1],
                strength=len(group),
            ))
        else:
            # Non-cardinal: use first and last in direction order
            angle_rad = math.radians(line_a.angle_deg)
            all_pts.sort(key=lambda p: p[0] * math.cos(angle_rad) + p[1] * math.sin(angle_rad))
            merged.append(DetectedLine(
                all_pts[0][0], all_pts[0][1],
                all_pts[-1][0], all_pts[-1][1],
                strength=len(group),
            ))

    logger.info(f"Merged {len(lines)} lines → {len(merged)} segments")
    return merged


def _snap_to_grid(
    lines: List[DetectedLine],
    grid_px: float,
) -> List[DetectedLine]:
    """Snap line endpoints to a regular grid."""
    def snap(val):
        return round(val / grid_px) * grid_px

    snapped = []
    for ln in lines:
        if ln.is_horizontal:
            y = snap(ln.y1)
            snapped.append(DetectedLine(snap(ln.x1), y, snap(ln.x2), y, ln.strength))
        elif ln.is_vertical:
            x = snap(ln.x1)
            snapped.append(DetectedLine(x, snap(ln.y1), x, snap(ln.y2), ln.strength))
        else:
            snapped.append(DetectedLine(
                snap(ln.x1), snap(ln.y1),
                snap(ln.x2), snap(ln.y2),
                ln.strength,
            ))
    return snapped


def _filter_walls(
    lines: List[DetectedLine],
    min_length_px: float = 30,
) -> List[DetectedLine]:
    """Filter lines to keep only probable wall segments."""
    walls = []
    for ln in lines:
        # Only keep cardinal directions (horizontal/vertical)
        if not ln.is_cardinal:
            continue
        # Minimum length
        if ln.length < min_length_px:
            continue
        walls.append(ln)
    return walls


def _pixel_to_model(
    lines: List[DetectedLine],
    image_width: int,
    image_height: int,
    scale_reference_m: float,
    reference_axis: str = "x",
) -> List[Tuple[Point2D, Point2D]]:
    """Convert pixel coordinates to model coordinates (meters).

    Args:
        lines: Lines in pixel coordinates
        image_width: Image width in pixels
        image_height: Image height in pixels
        scale_reference_m: Known real-world dimension for scaling
        reference_axis: Which axis the reference dimension applies to ("x" or "y")
    """
    # Find bounding box of all lines
    all_x = [ln.x1 for ln in lines] + [ln.x2 for ln in lines]
    all_y = [ln.y1 for ln in lines] + [ln.y2 for ln in lines]

    if not all_x:
        return []

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    span_x = max_x - min_x
    span_y = max_y - min_y

    if reference_axis == "x":
        px_per_m = span_x / scale_reference_m if scale_reference_m > 0 else 100
    else:
        px_per_m = span_y / scale_reference_m if scale_reference_m > 0 else 100

    result = []
    for ln in lines:
        x1 = (ln.x1 - min_x) / px_per_m
        y1 = (max_y - ln.y1) / px_per_m  # Flip Y axis (image Y is top-down)
        x2 = (ln.x2 - min_x) / px_per_m
        y2 = (max_y - ln.y2) / px_per_m
        result.append(((x1, y1), (x2, y2)))

    return result


def read_sketch(
    image_path: str,
    scale_reference_m: float = 7.0,
    reference_axis: str = "x",
    wall_material: str = "bloco_ceramico_14",
    ceiling_height: float = 2.80,
    config: Optional[SketchConfig] = None,
):
    """Read a sketch image and convert to BuildingModel.

    Args:
        image_path: Path to sketch image (jpg, png, etc.)
        scale_reference_m: Known real-world dimension for scaling (meters).
            This is the total width or depth of the building in the sketch.
        reference_axis: Which axis the reference applies to ("x" or "y")
        wall_material: Default wall material for detected walls
        ceiling_height: Default ceiling height
        config: Detection configuration

    Returns:
        BuildingModel with detected walls
    """
    import cv2

    if config is None:
        config = SketchConfig()

    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    h, w = image.shape[:2]
    logger.info(f"Processing sketch: {image_path} ({w}x{h})")

    # Pipeline
    binary = _preprocess(image)
    raw_lines = _detect_lines(binary, config)

    if not raw_lines:
        logger.warning("No lines detected in sketch")
        from .building_model import BuildingModel
        return BuildingModel(ceiling_height=ceiling_height)

    # Merge and clean
    merged = _merge_collinear(raw_lines, config)
    snapped = _snap_to_grid(merged, config.snap_grid_px)
    walls = _filter_walls(snapped, min_length_px=config.min_line_length_px * 0.5)

    # Convert to model coordinates
    wall_segments = _pixel_to_model(
        walls, w, h, scale_reference_m, reference_axis,
    )

    # Build model
    from .building_model import BuildingModel
    model = BuildingModel(
        ceiling_height=ceiling_height,
        default_wall_material=wall_material,
    )

    for p1, p2 in wall_segments:
        model.add_wall(p1, p2, material=wall_material)

    logger.info(
        f"Sketch reader: {len(raw_lines)} raw lines → "
        f"{len(merged)} merged → {len(walls)} walls → "
        f"BuildingModel with {len(model.walls)} walls"
    )

    return model


def read_sketch_to_dxf(
    image_path: str,
    output_path: str,
    scale_reference_m: float = 7.0,
    sheet_format: str = "A2",
    scale: str = "1:50",
    **kwargs,
) -> str:
    """Convenience: read sketch and directly produce a DXF.

    Args:
        image_path: Path to sketch image
        output_path: Path for output DXF
        scale_reference_m: Known dimension for scaling
        sheet_format: Sheet format (A0-A4)
        scale: Drawing scale

    Returns:
        Path to saved DXF file
    """
    from .sheet import TechnicalSheet, TitleBlockInfo

    model = read_sketch(image_path, scale_reference_m=scale_reference_m, **kwargs)

    sheet = TechnicalSheet(sheet_format, scale=scale)
    sheet.add_title_block(TitleBlockInfo(
        project="FROM SKETCH",
        drawing_title="PLANTA BAIXA (AUTO-DETECTED)",
        author="Escora.AI",
        date="AUTO",
        scale_str=scale,
        sheet_format=sheet_format,
    ))
    sheet.draw_plan(model, auto_dim=True)

    return sheet.save(output_path)
