"""Unified BuildingModel — single source of truth for all drawing views.

Every element references a real construction material. Each view generator
(plan, section, elevation, isometric) reads from this model instead of
receiving disconnected tuples.

Usage:
    from src.drawing.building_model import BuildingModel
    from src.drawing.materials import get_wall_material

    model = BuildingModel(ceiling_height=2.80)
    model.add_wall((0,0), (7,0), material="bloco_ceramico_14")
    model.add_wall((7,0), (7,10), material="bloco_ceramico_14")
    model.add_opening("door", wall_id=0, position=1.0, width=0.80, height=2.10)
    model.add_opening("window", wall_id=0, position=3.0, width=1.50, height=1.20, sill=1.00)
    model.add_slab(material="pre_moldada_12")
    model.set_roof(style="gable", material="ceramica_colonial", slope_pct=30)

    # Generate all views from the same model
    sheet.draw_plan(model)
    sheet.draw_section(model, cut)
    sheet.draw_elevation(model, "south")
    sheet.draw_isometric(model)
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from .materials import (
    WallMaterial, SlabMaterial, FoundationMaterial, RoofMaterial,
    StructuralMember,
    get_wall_material, get_slab_material, get_foundation_material,
    get_roof_material,
)
from .nbr import HatchMaterial

logger = logging.getLogger(__name__)

Point2D = Tuple[float, float]


# ---------------------------------------------------------------------------
# Opening types
# ---------------------------------------------------------------------------

class OpeningType(Enum):
    DOOR = "door"
    WINDOW = "window"
    GARAGE = "garage"


# ---------------------------------------------------------------------------
# Building elements
# ---------------------------------------------------------------------------

@dataclass
class WallSegment:
    """A wall segment with material reference."""
    id: int
    p1: Point2D
    p2: Point2D
    material: WallMaterial
    height_m: float = 2.80
    floor: int = 0               # Floor level (0 = ground)
    openings: List["Opening"] = field(default_factory=list)

    @property
    def thickness_m(self) -> float:
        return self.material.total_thickness_m

    @property
    def length_m(self) -> float:
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        return math.sqrt(dx**2 + dy**2)

    @property
    def direction(self) -> Tuple[float, float]:
        """Unit vector along wall."""
        l = self.length_m
        if l < 1e-6:
            return (1.0, 0.0)
        return ((self.p2[0] - self.p1[0]) / l,
                (self.p2[1] - self.p1[1]) / l)

    @property
    def normal(self) -> Tuple[float, float]:
        """Outward normal (perpendicular to direction, left-hand side)."""
        dx, dy = self.direction
        return (-dy, dx)

    @property
    def angle_deg(self) -> float:
        """Angle from +X axis in degrees."""
        dx, dy = self.direction
        return math.degrees(math.atan2(dy, dx))

    @property
    def area_m2(self) -> float:
        """Gross wall area (no opening deductions)."""
        return self.length_m * self.height_m

    @property
    def net_area_m2(self) -> float:
        """Net wall area (deducting openings)."""
        opening_area = sum(o.width * o.height for o in self.openings)
        return self.area_m2 - opening_area

    @property
    def weight_kn(self) -> float:
        """Total wall weight from material."""
        return self.net_area_m2 * self.material.weight_kn_m2

    @property
    def is_structural(self) -> bool:
        return self.material.is_structural

    @property
    def hatch(self) -> HatchMaterial:
        return self.material.hatch

    def corners(self) -> List[Point2D]:
        """4 corners of the wall rectangle (outer polygon)."""
        t = self.thickness_m / 2
        nx, ny = self.normal
        return [
            (self.p1[0] + nx * t, self.p1[1] + ny * t),
            (self.p2[0] + nx * t, self.p2[1] + ny * t),
            (self.p2[0] - nx * t, self.p2[1] - ny * t),
            (self.p1[0] - nx * t, self.p1[1] - ny * t),
        ]

    def point_at(self, distance: float) -> Point2D:
        """Point along wall at given distance from p1."""
        dx, dy = self.direction
        return (self.p1[0] + dx * distance, self.p1[1] + dy * distance)


@dataclass
class Opening:
    """Door, window, or garage opening in a wall."""
    id: int
    type: OpeningType
    wall_id: int
    position_m: float            # Distance from wall p1 to opening start
    width: float                 # Opening width (m)
    height: float                # Opening height (m)
    sill_height: float = 0.0     # Distance from floor to bottom of opening
    opening_side: str = "left"   # Door swing direction
    panel_count: int = 1         # Number of panels (1=single, 2=double)

    @property
    def is_door(self) -> bool:
        return self.type == OpeningType.DOOR

    @property
    def is_window(self) -> bool:
        return self.type == OpeningType.WINDOW

    @property
    def lintel_height(self) -> float:
        """Top of opening from floor level."""
        return self.sill_height + self.height


@dataclass
class SlabElement:
    """Floor or ceiling slab."""
    id: int
    material: SlabMaterial
    boundary: List[Point2D]      # Polygon defining slab edge
    floor: int = 0               # Floor level
    is_ceiling: bool = False     # True = ceiling of this floor

    @property
    def thickness_m(self) -> float:
        return self.material.total_thickness_m

    @property
    def area_m2(self) -> float:
        """Slab area using shoelace formula."""
        n = len(self.boundary)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.boundary[i][0] * self.boundary[j][1]
            area -= self.boundary[j][0] * self.boundary[i][1]
        return abs(area) / 2.0

    @property
    def weight_kn(self) -> float:
        return self.area_m2 * self.material.weight_kn_m2


class RoofStyle(Enum):
    GABLE = "gable"              # Duas águas
    HIP = "hip"                  # Quatro águas
    SHED = "shed"                # Uma água
    FLAT = "flat"                # Laje impermeabilizada


@dataclass
class RoofElement:
    """Roof definition."""
    style: RoofStyle = RoofStyle.GABLE
    material: Optional[RoofMaterial] = None
    slope_pct: float = 30.0      # Slope percentage
    overhang_m: float = 0.60     # Beiral
    ridge_direction: str = "x"   # Ridge runs along "x" or "y" axis

    @property
    def slope_deg(self) -> float:
        return math.degrees(math.atan(self.slope_pct / 100.0))

    @property
    def weight_kn_m2(self) -> float:
        if self.material:
            return self.material.weight_kn_m2
        return 0.50  # Default ceramic


@dataclass
class FoundationElement:
    """Foundation definition."""
    material: Optional[FoundationMaterial] = None
    depth_m: float = 0.40
    width_m: float = 0.60


@dataclass
class ColumnElement:
    """Structural column."""
    id: int
    position: Point2D
    member: StructuralMember
    height_m: float = 2.80
    floor: int = 0


@dataclass
class BeamElement:
    """Structural beam."""
    id: int
    p1: Point2D
    p2: Point2D
    member: StructuralMember
    elevation_m: float = 2.80    # Bottom of beam from floor
    floor: int = 0


@dataclass
class RoomLabel:
    """Room annotation."""
    name: str
    center: Point2D
    area_m2: float
    floor: int = 0
    finish: str = ""             # Piso: ceramica, porcelanato, cimento


# ---------------------------------------------------------------------------
# BuildingModel — unified model
# ---------------------------------------------------------------------------

class BuildingModel:
    """Unified building model — single source of truth for all views.

    Stores walls, openings, slabs, roof, foundation, columns, beams
    with real material references. Every view generator reads from here.
    """

    def __init__(
        self,
        ceiling_height: float = 2.80,
        default_wall_material: str = "bloco_ceramico_14",
        default_slab_material: str = "pre_moldada_12",
        floors: int = 1,
    ):
        self.ceiling_height = ceiling_height
        self.default_wall_material = default_wall_material
        self.default_slab_material = default_slab_material
        self.floors = floors

        self.walls: List[WallSegment] = []
        self.openings: List[Opening] = []
        self.slabs: List[SlabElement] = []
        self.roof: Optional[RoofElement] = None
        self.foundation: Optional[FoundationElement] = None
        self.columns: List[ColumnElement] = []
        self.beams: List[BeamElement] = []
        self.room_labels: List[RoomLabel] = []

        self._next_wall_id = 0
        self._next_opening_id = 0
        self._next_slab_id = 0
        self._next_col_id = 0
        self._next_beam_id = 0

    # -------------------------------------------------------------------
    # Add elements
    # -------------------------------------------------------------------

    def add_wall(
        self,
        p1: Point2D,
        p2: Point2D,
        material: Optional[str] = None,
        height: Optional[float] = None,
        floor: int = 0,
    ) -> int:
        """Add a wall segment. Returns wall ID."""
        mat = get_wall_material(material or self.default_wall_material)
        wall = WallSegment(
            id=self._next_wall_id,
            p1=p1,
            p2=p2,
            material=mat,
            height_m=height or self.ceiling_height,
            floor=floor,
        )
        self.walls.append(wall)
        self._next_wall_id += 1
        return wall.id

    def add_opening(
        self,
        type: str,
        wall_id: int,
        position: float,
        width: float,
        height: float,
        sill_height: float = 0.0,
        opening_side: str = "left",
        panel_count: int = 1,
    ) -> int:
        """Add an opening to a wall. Returns opening ID."""
        wall = self.get_wall(wall_id)
        if wall is None:
            raise ValueError(f"Wall {wall_id} not found")

        opening = Opening(
            id=self._next_opening_id,
            type=OpeningType(type),
            wall_id=wall_id,
            position_m=position,
            width=width,
            height=height,
            sill_height=sill_height,
            opening_side=opening_side,
            panel_count=panel_count,
        )
        wall.openings.append(opening)
        self.openings.append(opening)
        self._next_opening_id += 1
        return opening.id

    def add_slab(
        self,
        boundary: Optional[List[Point2D]] = None,
        material: Optional[str] = None,
        floor: int = 0,
        is_ceiling: bool = False,
    ) -> int:
        """Add a floor/ceiling slab. If boundary is None, uses wall bounding box."""
        if boundary is None:
            boundary = self._compute_bounding_polygon(floor)

        mat = get_slab_material(material or self.default_slab_material)
        slab = SlabElement(
            id=self._next_slab_id,
            material=mat,
            boundary=boundary,
            floor=floor,
            is_ceiling=is_ceiling,
        )
        self.slabs.append(slab)
        self._next_slab_id += 1
        return slab.id

    def set_roof(
        self,
        style: str = "gable",
        material: str = "ceramica_colonial",
        slope_pct: float = 30.0,
        overhang_m: float = 0.60,
        ridge_direction: str = "x",
    ) -> None:
        """Set the roof configuration."""
        self.roof = RoofElement(
            style=RoofStyle(style),
            material=get_roof_material(material),
            slope_pct=slope_pct,
            overhang_m=overhang_m,
            ridge_direction=ridge_direction,
        )

    def set_foundation(
        self,
        material: str = "sapata_corrida",
        depth_m: Optional[float] = None,
        width_m: Optional[float] = None,
    ) -> None:
        """Set the foundation configuration."""
        mat = get_foundation_material(material)
        self.foundation = FoundationElement(
            material=mat,
            depth_m=depth_m or mat.depth_m,
            width_m=width_m or mat.width_m,
        )

    def add_column(
        self,
        position: Point2D,
        member_id: str = "pilar_14x30",
        height: Optional[float] = None,
        floor: int = 0,
    ) -> int:
        """Add a structural column."""
        from .materials import COLUMN_PRESETS
        member = COLUMN_PRESETS.get(member_id)
        if member is None:
            raise ValueError(f"Column preset '{member_id}' not found")

        col = ColumnElement(
            id=self._next_col_id,
            position=position,
            member=member,
            height_m=height or self.ceiling_height,
            floor=floor,
        )
        self.columns.append(col)
        self._next_col_id += 1
        return col.id

    def add_beam(
        self,
        p1: Point2D,
        p2: Point2D,
        member_id: str = "viga_14x40",
        elevation: Optional[float] = None,
        floor: int = 0,
    ) -> int:
        """Add a structural beam."""
        from .materials import BEAM_PRESETS
        member = BEAM_PRESETS.get(member_id)
        if member is None:
            raise ValueError(f"Beam preset '{member_id}' not found")

        beam = BeamElement(
            id=self._next_beam_id,
            p1=p1,
            p2=p2,
            member=member,
            elevation_m=elevation or self.ceiling_height,
            floor=floor,
        )
        self.beams.append(beam)
        self._next_beam_id += 1
        return beam.id

    def add_room(
        self,
        name: str,
        center: Point2D,
        area_m2: float,
        floor: int = 0,
        finish: str = "",
    ) -> None:
        """Add a room label/annotation."""
        self.room_labels.append(RoomLabel(
            name=name, center=center, area_m2=area_m2,
            floor=floor, finish=finish,
        ))

    # -------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------

    def get_wall(self, wall_id: int) -> Optional[WallSegment]:
        for w in self.walls:
            if w.id == wall_id:
                return w
        return None

    def walls_on_floor(self, floor: int = 0) -> List[WallSegment]:
        return [w for w in self.walls if w.floor == floor]

    def openings_on_wall(self, wall_id: int) -> List[Opening]:
        wall = self.get_wall(wall_id)
        return wall.openings if wall else []

    def slabs_on_floor(self, floor: int = 0) -> List[SlabElement]:
        return [s for s in self.slabs if s.floor == floor]

    def columns_on_floor(self, floor: int = 0) -> List[ColumnElement]:
        return [c for c in self.columns if c.floor == floor]

    def beams_on_floor(self, floor: int = 0) -> List[BeamElement]:
        return [b for b in self.beams if b.floor == floor]

    def rooms_on_floor(self, floor: int = 0) -> List[RoomLabel]:
        return [r for r in self.room_labels if r.floor == floor]

    # -------------------------------------------------------------------
    # Computed properties
    # -------------------------------------------------------------------

    @property
    def bounding_box(self) -> Tuple[float, float, float, float]:
        """(x_min, y_min, x_max, y_max) of all walls."""
        if not self.walls:
            return (0, 0, 0, 0)
        xs = []
        ys = []
        for w in self.walls:
            xs.extend([w.p1[0], w.p2[0]])
            ys.extend([w.p1[1], w.p2[1]])
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def width_m(self) -> float:
        bb = self.bounding_box
        return bb[2] - bb[0]

    @property
    def depth_m(self) -> float:
        bb = self.bounding_box
        return bb[3] - bb[1]

    @property
    def total_height_m(self) -> float:
        """Total building height including roof."""
        h = self.ceiling_height * self.floors
        if self.roof and self.roof.style != RoofStyle.FLAT:
            # Approximate ridge height
            half_span = min(self.width_m, self.depth_m) / 2.0
            ridge_h = half_span * self.roof.slope_pct / 100.0
            h += ridge_h
        return h

    @property
    def built_area_m2(self) -> float:
        """Built area (footprint)."""
        return self.width_m * self.depth_m

    @property
    def total_wall_area_m2(self) -> float:
        return sum(w.net_area_m2 for w in self.walls)

    @property
    def total_wall_weight_kn(self) -> float:
        return sum(w.weight_kn for w in self.walls)

    @property
    def total_slab_weight_kn(self) -> float:
        return sum(s.weight_kn for s in self.slabs)

    @property
    def total_weight_kn(self) -> float:
        """Total dead load (walls + slabs + roof)."""
        w = self.total_wall_weight_kn + self.total_slab_weight_kn
        if self.roof:
            w += self.built_area_m2 * self.roof.weight_kn_m2
        return w

    def roof_profile(
        self, direction: str = "x"
    ) -> List[Point2D]:
        """Get the roof profile polygon for sections/elevations.

        Returns 2D points (position_along_span, height_above_ceiling).
        """
        if not self.roof or self.roof.style == RoofStyle.FLAT:
            return []

        bb = self.bounding_box
        ovh = self.roof.overhang_m if self.roof else 0
        slope = self.roof.slope_pct / 100.0
        ch = self.ceiling_height * self.floors

        if direction == "x":
            span = bb[3] - bb[1]  # depth
            x_start = bb[1] - ovh
            x_end = bb[3] + ovh
        else:
            span = bb[2] - bb[0]  # width
            x_start = bb[0] - ovh
            x_end = bb[2] + ovh

        if self.roof.style == RoofStyle.GABLE:
            mid = (x_start + x_end) / 2
            ridge_h = (span / 2 + ovh) * slope
            return [
                (x_start, ch),
                (mid, ch + ridge_h),
                (x_end, ch),
            ]
        elif self.roof.style == RoofStyle.SHED:
            rise = (span + 2 * ovh) * slope
            return [
                (x_start, ch),
                (x_end, ch + rise),
            ]
        elif self.roof.style == RoofStyle.HIP:
            # Simplified: same as gable from both directions
            mid = (x_start + x_end) / 2
            ridge_h = (span / 2 + ovh) * slope
            return [
                (x_start, ch),
                (mid, ch + ridge_h),
                (x_end, ch),
            ]

        return []

    # -------------------------------------------------------------------
    # Export helpers (for view generators)
    # -------------------------------------------------------------------

    def walls_as_tuples(self, floor: int = 0):
        """Export walls as (p1, p2, height, thickness) for legacy view generators."""
        return [
            (w.p1, w.p2, w.height_m, w.thickness_m)
            for w in self.walls_on_floor(floor)
        ]

    def openings_as_dicts(self, floor: int = 0) -> List[dict]:
        """Export openings as dicts for elevation generator."""
        result = []
        for w in self.walls_on_floor(floor):
            mid_x = (w.p1[0] + w.p2[0]) / 2
            mid_y = (w.p1[1] + w.p2[1]) / 2
            for o in w.openings:
                pt = w.point_at(o.position_m)
                result.append({
                    "type": o.type.value,
                    "x": pt[0],
                    "y": pt[1],
                    "width": o.width,
                    "height": o.height,
                    "sill_height": o.sill_height,
                    "opening_side": o.opening_side,
                    "wall_angle": w.angle_deg,
                    "wall_mid_x": mid_x,
                    "wall_mid_y": mid_y,
                })
        return result

    # -------------------------------------------------------------------
    # Bill of Materials
    # -------------------------------------------------------------------

    def bill_of_materials(self) -> List[dict]:
        """Generate a bill of materials from the model."""
        bom = []

        # Walls grouped by material
        wall_groups: Dict[str, dict] = {}
        for w in self.walls:
            key = w.material.id
            if key not in wall_groups:
                wall_groups[key] = {
                    "category": "Paredes",
                    "material": w.material.name_pt,
                    "thickness_cm": w.material.total_thickness_cm,
                    "area_m2": 0.0,
                    "weight_kn": 0.0,
                    "unit": "m²",
                }
            wall_groups[key]["area_m2"] += w.net_area_m2
            wall_groups[key]["weight_kn"] += w.weight_kn

        for g in wall_groups.values():
            g["area_m2"] = round(g["area_m2"], 2)
            g["weight_kn"] = round(g["weight_kn"], 2)
            g["quantity"] = g["area_m2"]
            bom.append(g)

        # Slabs
        for s in self.slabs:
            bom.append({
                "category": "Lajes",
                "material": s.material.name_pt,
                "thickness_cm": s.material.total_thickness_cm,
                "area_m2": round(s.area_m2, 2),
                "weight_kn": round(s.weight_kn, 2),
                "unit": "m²",
                "quantity": round(s.area_m2, 2),
            })

        # Roof
        if self.roof and self.roof.material:
            roof_area = self.built_area_m2 / math.cos(math.radians(self.roof.slope_deg))
            bom.append({
                "category": "Cobertura",
                "material": self.roof.material.name_pt,
                "area_m2": round(roof_area, 2),
                "weight_kn": round(roof_area * self.roof.weight_kn_m2, 2),
                "unit": "m²",
                "quantity": round(roof_area, 2),
            })

        # Foundation
        if self.foundation and self.foundation.material:
            # Linear meters of foundation = perimeter of structural walls
            perim = sum(w.length_m for w in self.walls if w.is_structural)
            bom.append({
                "category": "Fundação",
                "material": self.foundation.material.name_pt,
                "length_m": round(perim, 2),
                "depth_m": self.foundation.depth_m,
                "width_m": self.foundation.width_m,
                "unit": "m",
                "quantity": round(perim, 2),
            })

        return bom

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _compute_bounding_polygon(self, floor: int = 0) -> List[Point2D]:
        """Compute bounding rectangle from walls on a floor."""
        walls = self.walls_on_floor(floor)
        if not walls:
            return [(0, 0), (1, 0), (1, 1), (0, 1)]
        xs = []
        ys = []
        for w in walls:
            xs.extend([w.p1[0], w.p2[0]])
            ys.extend([w.p1[1], w.p2[1]])
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def __repr__(self) -> str:
        return (
            f"BuildingModel(walls={len(self.walls)}, openings={len(self.openings)}, "
            f"slabs={len(self.slabs)}, floors={self.floors}, "
            f"area={self.built_area_m2:.1f}m², weight={self.total_weight_kn:.1f}kN)"
        )
