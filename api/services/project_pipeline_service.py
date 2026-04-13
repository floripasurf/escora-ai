"""Pipeline service para projetos de alvenaria estrutural.

Orquestra o fluxo completo:
  Input -> Layout -> Calculos -> DXFs -> BOM -> PDF -> Assembler
"""

import logging
import math
from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional

from src.models.masonry import ProjectInput, MasonryProject
from src.layout.solver import solve_layout
from src.layout.modular_grid import get_module, blocks_in_wall
from src.output.arch_dxf_generator import generate_architectural_dxf
from src.output.structural_dxf_generator import generate_structural_dxf
from src.output.project_assembler import assemble_project
from src.generator.masonry_bom_generator import (
    calculate_masonry_bom, write_masonry_bom_csv,
)
from src.output.masonry_pdf_generator import generate_masonry_memorial
from src.utils.masonry_constants import BLOCO_14_DIMS, BLOCO_19_DIMS

logger = logging.getLogger(__name__)


def process_project(
    input_data: dict,
    project_id: str,
    output_dir: str,
) -> Dict[str, Any]:
    """Executa o pipeline completo de geracao de projeto.

    Args:
        input_data: Dict com dados do formulario (sera convertido a ProjectInput)
        project_id: ID unico do projeto
        output_dir: Diretorio base de saida

    Returns:
        Dict com caminhos dos arquivos gerados e resumo do projeto
    """
    try:
        # 1. Validate input
        project_input = ProjectInput(**input_data)
        logger.info(
            f"Projeto {project_id}: {project_input.bedrooms}q, "
            f"{project_input.target_area_m2}m2, "
            f"bloco {project_input.block_size.value}cm"
        )

        # 2. Generate layout
        floor_plan = solve_layout(project_input)
        logger.info(
            f"Layout: {floor_plan.width_m:.2f}x{floor_plan.depth_m:.2f}m, "
            f"{len(floor_plan.rooms)} comodos, {len(floor_plan.walls)} paredes"
        )

        # 3. Calculate structural loads
        floor_plan, fbk = calculate_masonry_project(project_input, floor_plan)

        # 4. Design foundations
        foundations = design_foundations(
            floor_plan,
            soil_capacity_kpa=project_input.soil_capacity_kpa,
        )

        # 5. Calculate total blocks
        module = get_module(project_input.block_size.value)
        block_dims = (
            BLOCO_14_DIMS
            if project_input.block_size.value == "14"
            else BLOCO_19_DIMS
        )

        total_blocks = 0
        total_wall_area = 0.0
        for wall in floor_plan.walls:
            if wall.is_structural:
                total_wall_area += wall.net_area_m2
                info = blocks_in_wall(
                    wall.length_m, wall.height_m, block_dims
                )
                total_blocks += info["blocos_inteiros"] + info["meios_blocos"]

        # Add waste
        total_blocks = math.ceil(total_blocks * 1.05)

        # 6. Assemble project model
        project = MasonryProject(
            input=project_input,
            floor_plans=[floor_plan],
            foundations=foundations,
            block_fbk_mpa=fbk,
            total_block_count=total_blocks,
            total_wall_area_m2=round(total_wall_area, 1),
            warnings=_collect_warnings(floor_plan, foundations, fbk),
        )

        # 7. Generate outputs
        out_dir = Path(output_dir) / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = (
            f"projeto_{project_input.bedrooms}q_"
            f"{int(project_input.target_area_m2)}m2"
        )

        # Architectural DXF
        arch_dxf_path = str(out_dir / f"{stem}_arquitetonico.dxf")
        generate_architectural_dxf(floor_plan, arch_dxf_path)

        # Structural DXF
        struct_dxf_path = str(out_dir / f"{stem}_estrutural.dxf")
        generate_structural_dxf(project, struct_dxf_path)

        # BOM CSV
        bom_csv_path = str(out_dir / f"{stem}_materiais.csv")
        write_masonry_bom_csv(project, bom_csv_path)

        # Memorial PDF
        memorial_pdf_path = str(out_dir / f"{stem}_memorial.pdf")
        generate_masonry_memorial(project, memorial_pdf_path)

        # IFC BIM model (optional — may fail on some Python versions)
        ifc_path = None
        try:
            from src.output.ifc_generator import generate_masonry_ifc
            ifc_path = str(out_dir / f"{stem}.ifc")
            generate_masonry_ifc(project, ifc_path)
        except Exception as exc:
            logger.warning(f"IFC generation skipped: {exc}")
            ifc_path = None

        # ZIP assembly
        zip_files = {
            "arch_dxf": arch_dxf_path,
            "struct_dxf": struct_dxf_path,
            "memorial_pdf": memorial_pdf_path,
            "bom_csv": bom_csv_path,
        }
        if ifc_path and Path(ifc_path).exists():
            zip_files["ifc"] = ifc_path
        zip_path = assemble_project(str(out_dir), stem, zip_files)

        # 8. Build preview data (simplified geometry for frontend SVG)
        preview = _build_preview(floor_plan)

        # 9. Build result summary
        result = {
            "status": "done",
            "project_id": project_id,
            "arch_dxf_path": arch_dxf_path,
            "struct_dxf_path": struct_dxf_path,
            "bom_csv_path": bom_csv_path,
            "memorial_pdf_path": memorial_pdf_path,
            "ifc_path": ifc_path,
            "zip_path": zip_path,
            "preview": preview,
            "summary": {
                "width_m": floor_plan.width_m,
                "depth_m": floor_plan.depth_m,
                "area_m2": round(
                    floor_plan.width_m * floor_plan.depth_m, 1
                ),
                "rooms": len(floor_plan.rooms),
                "walls": len(floor_plan.walls),
                "block_fbk_mpa": fbk,
                "block_size_cm": int(project_input.block_size.value),
                "total_blocks": total_blocks,
                "total_wall_area_m2": round(total_wall_area, 1),
                "foundation_type": (
                    foundations[0].type.value if foundations else "unknown"
                ),
                "warnings": project.warnings[:20],
            },
        }

        logger.info(f"Projeto {project_id} concluido com sucesso")
        return result

    except Exception as e:
        logger.exception(f"Projeto {project_id} falhou")
        return {
            "status": "error",
            "project_id": project_id,
            "error": str(e),
        }


def _collect_warnings(floor_plan, foundations, fbk):
    """Coleta avisos e alertas do projeto."""
    warnings = []

    # Check room areas
    from src.utils.masonry_constants import MIN_ROOM_AREAS
    for room in floor_plan.rooms:
        min_area = MIN_ROOM_AREAS.get(room.type.value, 2.0)
        if room.area_m2 < min_area * 0.95:
            warnings.append(
                f"{room.name}: area {room.area_m2:.1f}m2 "
                f"< minimo {min_area:.1f}m2"
            )

    # Check if max block strength was needed
    if fbk >= 12.0:
        warnings.append(
            f"Bloco fbk={fbk:.1f} MPa necessario "
            f"-- verificar viabilidade regional"
        )

    # Check foundation widths
    for f in foundations:
        if f.width_m > 0.80:
            warnings.append(
                f"Fundacao B={f.width_m:.2f}m > 0.80m "
                f"-- considerar radier"
            )

    return warnings


def _build_preview(floor_plan):
    """Gera dados simplificados para preview SVG no frontend."""
    rooms_data = []
    for room in floor_plan.rooms:
        if len(room.polygon) < 3:
            continue
        rooms_data.append({
            "name": room.name,
            "type": room.type.value,
            "polygon": room.polygon,
            "area_m2": round(room.area_m2, 1),
            "is_wet": room.is_wet,
        })

    walls_data = []
    for wall in floor_plan.walls:
        walls_data.append({
            "id": wall.id,
            "start": wall.start,
            "end": wall.end,
            "thickness_m": wall.thickness_m,
            "is_structural": wall.is_structural,
            "openings": [
                {
                    "type": o.type.value,
                    "width_m": o.width_m,
                    "position_m": o.position_m,
                }
                for o in wall.openings
            ],
        })

    # Build driveway/access data for garage rooms
    access_data = None
    for room in floor_plan.rooms:
        if room.type.value == 'garage':
            xs = [p[0] for p in room.polygon]
            ys = [p[1] for p in room.polygon]
            access_data = {
                "garage_bounds": {
                    "x0": min(xs), "y0": min(ys),
                    "x1": max(xs), "y1": max(ys),
                },
                "has_garage": True,
            }
            break

    result = {
        "width_m": floor_plan.width_m,
        "depth_m": floor_plan.depth_m,
        "rooms": rooms_data,
        "walls": walls_data,
    }
    if access_data:
        result["vehicle_access"] = access_data
    return result
