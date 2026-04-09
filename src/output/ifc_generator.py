"""IFC 4 export for Escora.AI shoring calculations.

Produces a BIM-compatible .ifc file containing:
- IfcProject / IfcSite / IfcBuilding / IfcBuildingStorey
- IfcSlab     — concrete slab panels (extruded polygons)
- IfcBeam     — concrete beams (extruded rectangular sections)
- IfcColumn   — concrete pillars (extruded rectangular sections)
- IfcMember   — telescopic shores (thin cylinders, PredefinedType=POST)
- IfcMember   — shoring towers (thin boxes, PredefinedType=POST)

The resulting .ifc opens cleanly in Revit, BricsCAD BIM, BIMcollab,
BlenderBIM, FreeCAD, and any other IFC4 viewer.
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import ifcopenshell
import ifcopenshell.api

from src.models.calculation_models import CalculationResult
from src.models.pipeline_models import ClassifiedElement, ElementType, PipelineResult
from src.models.shore import SupportType

logger = logging.getLogger(__name__)


# -------- Low-level helpers --------------------------------------------------

def _run(action: str, ifc, **kwargs):
    return ifcopenshell.api.run(action, ifc, **kwargs)


def _point3d(ifc, xyz: Tuple[float, float, float]):
    return ifc.createIfcCartesianPoint([float(xyz[0]), float(xyz[1]), float(xyz[2])])


def _dir3d(ifc, xyz: Tuple[float, float, float]):
    return ifc.createIfcDirection([float(xyz[0]), float(xyz[1]), float(xyz[2])])


def _axis2_placement_3d(
    ifc,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    axis: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    ref_direction: Tuple[float, float, float] = (1.0, 0.0, 0.0),
):
    return ifc.createIfcAxis2Placement3D(
        _point3d(ifc, location),
        _dir3d(ifc, axis),
        _dir3d(ifc, ref_direction),
    )


def _local_placement(ifc, parent_placement, location: Tuple[float, float, float]):
    return ifc.createIfcLocalPlacement(
        parent_placement,
        _axis2_placement_3d(ifc, location=location),
    )


def _rect_profile(ifc, width_m: float, depth_m: float, name: str = "Rect"):
    placement = ifc.createIfcAxis2Placement2D(
        ifc.createIfcCartesianPoint([0.0, 0.0]),
        ifc.createIfcDirection([1.0, 0.0]),
    )
    return ifc.createIfcRectangleProfileDef(
        "AREA", name, placement, float(width_m), float(depth_m)
    )


def _circle_profile(ifc, radius_m: float, name: str = "Circle"):
    placement = ifc.createIfcAxis2Placement2D(
        ifc.createIfcCartesianPoint([0.0, 0.0]),
        ifc.createIfcDirection([1.0, 0.0]),
    )
    return ifc.createIfcCircleProfileDef("AREA", name, placement, float(radius_m))


def _arbitrary_profile(ifc, points_xy: Sequence[Tuple[float, float]], name: str = "Poly"):
    # Close the ring if the caller didn't
    pts = list(points_xy)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    ifc_points = [ifc.createIfcCartesianPoint([float(x), float(y)]) for x, y in pts]
    curve = ifc.createIfcPolyline(ifc_points)
    return ifc.createIfcArbitraryClosedProfileDef("AREA", name, curve)


def _extruded_solid(ifc, profile, depth_m: float, direction=(0.0, 0.0, 1.0)):
    placement = _axis2_placement_3d(ifc)
    return ifc.createIfcExtrudedAreaSolid(
        profile, placement, _dir3d(ifc, direction), float(depth_m)
    )


def _shape_representation(ifc, context, solids, rep_type: str = "SweptSolid"):
    return ifc.createIfcShapeRepresentation(
        context, "Body", rep_type, solids
    )


def _assign_product_representation(ifc, product, context, solid):
    rep = _shape_representation(ifc, context, [solid])
    shape = ifc.createIfcProductDefinitionShape(None, None, [rep])
    product.Representation = shape


# -------- Public entry point -------------------------------------------------

def generate_ifc(
    pipeline_result: PipelineResult,
    output_path: str,
    project_name: Optional[str] = None,
) -> str:
    """Write an IFC4 file summarizing the shoring calculation.

    Args:
        pipeline_result: Full pipeline result (levels, calculation, scale, warnings).
        output_path: Destination .ifc path.
        project_name: Optional project name (defaults to the DXF filename stem).

    Returns the output path on success.
    """
    calc: Optional[CalculationResult] = pipeline_result.calculation
    if calc is None:
        raise ValueError("Pipeline result has no calculation — nothing to export")

    stem = project_name or Path(pipeline_result.filename).stem

    # 1. Bootstrap a valid IFC4 file (project, units, context, owner history)
    ifc = ifcopenshell.api.run(
        "project.create_file",
        version="IFC4",
    )
    project = _run(
        "root.create_entity", ifc, ifc_class="IfcProject", name=f"Escora.AI — {stem}"
    )
    _run("unit.assign_unit", ifc, length={"is_metric": True, "raw": "METERS"})

    # Representation context for body geometry
    model_context = _run("context.add_context", ifc, context_type="Model")
    body_context = _run(
        "context.add_context",
        ifc,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )

    # Spatial structure: Site → Building → Storey
    site = _run("root.create_entity", ifc, ifc_class="IfcSite", name="Obra")
    building = _run(
        "root.create_entity", ifc, ifc_class="IfcBuilding", name="Edificação"
    )
    storey = _run(
        "root.create_entity", ifc, ifc_class="IfcBuildingStorey", name="Pavimento"
    )
    _run("aggregate.assign_object", ifc, relating_object=project, products=[site])
    _run("aggregate.assign_object", ifc, relating_object=site, products=[building])
    _run("aggregate.assign_object", ifc, relating_object=building, products=[storey])

    storey_placement = storey.ObjectPlacement  # created by the API above

    # Pull classified elements for the single-storey MVP
    pillars, beams = [], []
    if pipeline_result.levels:
        for lvl in pipeline_result.levels:
            for e in lvl.elements:
                if e.element_type == ElementType.PILLAR:
                    pillars.append(e)
                elif e.element_type == ElementType.BEAM:
                    beams.append(e)

    pe_direito = calc.pe_direito_m or 2.80

    created = {"slabs": 0, "beams": 0, "columns": 0, "shores": 0, "towers": 0}

    # 2. Slabs (extruded from their polygon, downward by thickness)
    for idx, sr in enumerate(calc.slab_results):
        try:
            pts = _polygon_to_xy(sr.polygon)
            if not pts or len(pts) < 3:
                continue
            profile = _arbitrary_profile(ifc, pts, name=f"Laje_{idx+1}")
            thickness = max(sr.thickness_m or 0.12, 0.05)
            # Place slab top at storey ceiling (= pe_direito), extrude downward
            solid = _extruded_solid(ifc, profile, depth_m=thickness)
            slab = _run(
                "root.create_entity",
                ifc,
                ifc_class="IfcSlab",
                name=f"Laje {idx+1} ({sr.area_m2:.1f} m²)",
            )
            slab.PredefinedType = "FLOOR"
            slab.ObjectPlacement = _local_placement(
                ifc, storey_placement, (0.0, 0.0, pe_direito - thickness)
            )
            _assign_product_representation(ifc, slab, body_context, solid)
            _run(
                "spatial.assign_container",
                ifc,
                relating_structure=storey,
                products=[slab],
            )
            created["slabs"] += 1
        except Exception as exc:
            logger.warning(f"IFC: skipping slab {idx+1}: {exc}")

    # 3. Beams (extruded rectangular section along axis line)
    for br in calc.beam_results:
        b = br.beam
        if not b.geometry or len(b.geometry) < 2:
            continue
        (x1, y1), (x2, y2) = b.geometry[0], b.geometry[1]
        length = math.hypot(x2 - x1, y2 - y1)
        if length <= 0:
            continue
        width = b.section_width_m or 0.14
        height = b.section_height_m or 0.40
        try:
            profile = _rect_profile(ifc, width, height, name="BeamSection")
            # Build an explicit axis2placement so the beam points along its axis
            # (extrusion is along local +Z of this placement)
            angle = math.atan2(y2 - y1, x2 - x1)
            # local Z = beam axis direction, local X = vertical (up)
            axis_x = math.cos(angle)
            axis_y = math.sin(angle)
            # Beam local coordinate system:
            #   local +Z = along the beam axis (so extrusion runs along the beam)
            #   local +X = global +Z (so the rectangle "height" points up)
            local_z = (axis_x, axis_y, 0.0)
            local_x = (0.0, 0.0, 1.0)
            placement_3d = ifc.createIfcAxis2Placement3D(
                _point3d(ifc, (x1, y1, pe_direito - height)),
                _dir3d(ifc, local_z),
                _dir3d(ifc, local_x),
            )
            local_placement = ifc.createIfcLocalPlacement(
                storey_placement, placement_3d
            )
            extrusion_placement = _axis2_placement_3d(ifc)
            solid = ifc.createIfcExtrudedAreaSolid(
                profile,
                extrusion_placement,
                _dir3d(ifc, (0.0, 0.0, 1.0)),  # extrude along the local Z
                float(length),
            )
            beam = _run(
                "root.create_entity",
                ifc,
                ifc_class="IfcBeam",
                name=b.name or f"V ({length:.1f} m)",
            )
            beam.PredefinedType = "BEAM"
            beam.ObjectPlacement = local_placement
            _assign_product_representation(ifc, beam, body_context, solid)
            _run(
                "spatial.assign_container",
                ifc,
                relating_structure=storey,
                products=[beam],
            )
            created["beams"] += 1
        except Exception as exc:
            logger.warning(f"IFC: skipping beam {b.name or '—'}: {exc}")

    # 4. Pillars (extruded upward over pé-direito)
    for p in pillars:
        if not p.geometry:
            continue
        cx, cy = p.geometry[0]
        width = p.section_width_m or 0.20
        depth = p.section_height_m or 0.20
        try:
            profile = _rect_profile(ifc, width, depth, name="PillarSection")
            solid = _extruded_solid(ifc, profile, depth_m=pe_direito)
            column = _run(
                "root.create_entity",
                ifc,
                ifc_class="IfcColumn",
                name=p.name or "Pilar",
            )
            column.PredefinedType = "COLUMN"
            column.ObjectPlacement = _local_placement(
                ifc, storey_placement, (cx, cy, 0.0)
            )
            _assign_product_representation(ifc, column, body_context, solid)
            _run(
                "spatial.assign_container",
                ifc,
                relating_structure=storey,
                products=[column],
            )
            created["columns"] += 1
        except Exception as exc:
            logger.warning(f"IFC: skipping pillar {p.name or '—'}: {exc}")

    # 5. Shores & towers — every PositionedShore becomes an IfcMember
    shore_radius = 0.03  # 6 cm diameter telescopic shore
    tower_half_side = 0.60  # ~1.2 m square footprint tower grid cell
    for br in calc.beam_results:
        for s in br.shores:
            _add_shore_member(
                ifc, body_context, storey, storey_placement,
                x=s.x, y=s.y,
                height_m=br.shore_height_m or (pe_direito - 0.40),
                support_type=s.support_type,
                shore_radius=shore_radius,
                tower_half_side=tower_half_side,
                name=f"Escora viga {br.beam.name or ''}".strip(),
            )
            created["shores" if s.support_type == SupportType.TELESCOPIC else "towers"] += 1

    for i, sr in enumerate(calc.slab_results):
        slab_shore_height = max(pe_direito - (sr.thickness_m or 0.12), 0.1)
        for s in sr.shores:
            _add_shore_member(
                ifc, body_context, storey, storey_placement,
                x=s.x, y=s.y,
                height_m=slab_shore_height,
                support_type=s.support_type,
                shore_radius=shore_radius,
                tower_half_side=tower_half_side,
                name=f"Escora laje {i+1}",
            )
            created["shores" if s.support_type == SupportType.TELESCOPIC else "towers"] += 1

    # 5b. Accessories — cruzetas as IfcBuildingElementProxy under one assembly
    try:
            compute_cruzeta_bom, load_tower_catalog,
        )
        _, _, accessories = load_tower_catalog()
        telescopic_counts: dict = {}
        tower_count = 0
        for br in calc.beam_results:
            for s in br.shores:
                if s.support_type == SupportType.TOWER:
                    tower_count += 1
                else:
                    telescopic_counts[s.shore.id] = telescopic_counts.get(s.shore.id, 0) + 1
        for sr in calc.slab_results:
            for s in sr.shores:
                if s.support_type == SupportType.TOWER:
                    tower_count += 1
                else:
                    telescopic_counts[s.shore.id] = telescopic_counts.get(s.shore.id, 0) + 1
        cruzeta_pairs = compute_cruzeta_bom(accessories, telescopic_counts, tower_count)
        accessory_count = 0
        for acc, qty in cruzeta_pairs:
            for i in range(int(qty)):
                proxy = _run(
                    "root.create_entity",
                    ifc,
                    ifc_class="IfcBuildingElementProxy",
                    name=f"{acc.model} #{i+1}",
                )
                proxy.ObjectType = "Cruzeta"
                proxy.ObjectPlacement = _local_placement(
                    ifc, storey_placement, (0.0, 0.0, 0.0)
                )
                _run(
                    "spatial.assign_container",
                    ifc,
                    relating_structure=storey,
                    products=[proxy],
                )
                accessory_count += 1
        if accessory_count:
            logger.info(f"IFC: added {accessory_count} cruzeta proxies")
    except Exception as exc:
        logger.warning(f"IFC: cruzeta accessories skipped: {exc}")

    # 6. Write out
    ifc.write(output_path)
    logger.info(
        f"IFC: wrote {output_path} "
        f"(slabs={created['slabs']}, beams={created['beams']}, "
        f"columns={created['columns']}, shores={created['shores']}, "
        f"towers={created['towers']})"
    )
    return output_path


def _add_shore_member(
    ifc, body_context, storey, storey_placement,
    *,
    x: float,
    y: float,
    height_m: float,
    support_type: SupportType,
    shore_radius: float,
    tower_half_side: float,
    name: str,
):
    """Create a telescopic shore (cylinder) or a tower post (square column)."""
    try:
        if support_type == SupportType.TOWER:
            profile = _rect_profile(
                ifc, tower_half_side * 2, tower_half_side * 2, name="TowerPost"
            )
            predefined = "POST"
            label = name or "Torre"
        else:
            profile = _circle_profile(ifc, shore_radius, name="ShoreCyl")
            predefined = "POST"
            label = name or "Escora"
        solid = _extruded_solid(ifc, profile, depth_m=max(height_m, 0.1))
        member = _run(
            "root.create_entity", ifc, ifc_class="IfcMember", name=label
        )
        member.PredefinedType = predefined
        member.ObjectPlacement = _local_placement(
            ifc, storey_placement, (x, y, 0.0)
        )
        _assign_product_representation(ifc, member, body_context, solid)
        _run(
            "spatial.assign_container",
            ifc,
            relating_structure=storey,
            products=[member],
        )
    except Exception as exc:
        logger.warning(f"IFC: skipping shore at ({x:.2f}, {y:.2f}): {exc}")


def _polygon_to_xy(polygon) -> List[Tuple[float, float]]:
    """Extract the exterior ring of a Shapely polygon as a list of (x,y)."""
    if polygon is None:
        return []
    try:
        coords = list(polygon.exterior.coords)
    except AttributeError:
        return []
    # Drop Z if present, drop duplicate closing point
    cleaned: List[Tuple[float, float]] = []
    for c in coords:
        cleaned.append((float(c[0]), float(c[1])))
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1]:
        cleaned = cleaned[:-1]
    return cleaned
