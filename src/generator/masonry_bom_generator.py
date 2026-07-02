"""Geração de lista de materiais para alvenaria estrutural.

Calcula quantidades de:
- Blocos estruturais (inteiros + meios-blocos + canaletas)
- Argamassa de assentamento
- Graute para cintas e vergas
- Aço para armaduras (cintas, vergas, fundação)
- Concreto de fundação

Referência: NBR 15961-1:2011 + práticas de orçamento MCMV
"""

import csv
import logging
import math
from typing import List, Dict, Any

from src.models.masonry import MasonryProject, FoundationType
from src.utils.masonry_constants import (
    BLOCO_14_DIMS, BLOCO_19_DIMS, MEIO_BLOCO_14, MEIO_BLOCO_19,
    JUNTA_ARGAMASSA, CINTA_RESPALDO_ALTURA,
)

logger = logging.getLogger(__name__)

# Waste factors
WASTE_BLOCKS = 0.05    # 5% desperdício de blocos
WASTE_MORTAR = 0.10    # 10% desperdício de argamassa
WASTE_REBAR = 0.10     # 10% para cortes e emendas


def calculate_masonry_bom(project: MasonryProject) -> List[Dict[str, Any]]:
    """Gera BOM completa para o projeto de alvenaria.

    Returns:
        Lista de dicts com materiais e quantidades
    """
    bom = []
    thickness_cm = int(project.input.block_size.value)

    if thickness_cm == 14:
        block_dims = BLOCO_14_DIMS
        half_dims = MEIO_BLOCO_14
    else:
        block_dims = BLOCO_19_DIMS
        half_dims = MEIO_BLOCO_19

    total_wall_area = 0.0
    total_opening_area = 0.0
    total_canaleta_m = 0.0
    total_verga_m = 0.0

    for floor in project.floor_plans:
        for wall in floor.walls:
            if not wall.is_structural:
                continue

            # Wall area
            wall_area = wall.net_area_m2
            total_wall_area += wall_area
            total_opening_area += sum(
                o.width_m * o.height_m for o in wall.openings
            )

        # Canaleta for tie beams
        for tb in floor.tie_beams:
            path_length = 0.0
            for i in range(len(tb.path) - 1):
                dx = tb.path[i+1][0] - tb.path[i][0]
                dy = tb.path[i+1][1] - tb.path[i][1]
                path_length += math.hypot(dx, dy)
            total_canaleta_m += path_length

        # Canaleta for lintels
        for lintel in floor.lintels:
            total_verga_m += lintel.span_m

    # === BLOCKS ===
    block_w, block_h, block_l = block_dims
    modulo_h = block_l + JUNTA_ARGAMASSA  # 0.40m
    modulo_v = block_h + JUNTA_ARGAMASSA  # 0.20m

    # Blocks per m² of wall
    blocks_per_m2 = 1.0 / (modulo_h * modulo_v)  # ~12.5 blocks/m²

    total_blocks = math.ceil(total_wall_area * blocks_per_m2 * (1 + WASTE_BLOCKS))
    half_blocks = math.ceil(total_blocks * 0.10)  # ~10% meios-blocos for bonding

    # Canaleta blocks (for tie beams and lintels)
    canaleta_per_m = 1.0 / modulo_h  # ~2.5 per meter
    total_canaletas = math.ceil(
        (total_canaleta_m + total_verga_m) * canaleta_per_m * (1 + WASTE_BLOCKS)
    )

    bom.append({
        "categoria": "Alvenaria",
        "material": f"Bloco estrutural {thickness_cm}×19×39cm",
        "unidade": "un",
        "quantidade": total_blocks,
        "observacao": f"fbk ≥ {project.block_fbk_mpa:.1f} MPa",
    })

    bom.append({
        "categoria": "Alvenaria",
        "material": f"Meio-bloco {thickness_cm}×19×19cm",
        "unidade": "un",
        "quantidade": half_blocks,
        "observacao": "Amarração de fiadas",
    })

    bom.append({
        "categoria": "Alvenaria",
        "material": f"Canaleta {thickness_cm}×19×39cm",
        "unidade": "un",
        "quantidade": total_canaletas,
        "observacao": "Cintas e vergas",
    })

    # === MORTAR ===
    # Approx 0.01 m³ per m² of wall (10mm joints)
    mortar_m3 = total_wall_area * 0.01 * (1 + WASTE_MORTAR)

    bom.append({
        "categoria": "Argamassa",
        "material": "Argamassa de assentamento (1:1:6 ou industrializada)",
        "unidade": "m³",
        "quantidade": round(mortar_m3, 2),
        "observacao": "Junta 10mm",
    })

    # === GROUT ===
    # Volume de graute = comprimento de canaleta × seção interna
    # Seção interna ~10×15cm para bloco 14, ~14×15cm para bloco 19
    secao_graute = (block_w - 0.04) * CINTA_RESPALDO_ALTURA
    graute_cintas_m3 = total_canaleta_m * secao_graute
    graute_vergas_m3 = total_verga_m * secao_graute
    graute_total_m3 = (graute_cintas_m3 + graute_vergas_m3) * (1 + WASTE_MORTAR)

    bom.append({
        "categoria": "Graute",
        "material": "Graute fck ≥ 15 MPa",
        "unidade": "m³",
        "quantidade": round(graute_total_m3, 2),
        "observacao": "Preenchimento de cintas e vergas",
    })

    # === REBAR ===
    # Cintas: 4φ8mm + estribos φ5c/20
    rebar_8mm_m = (total_canaleta_m + total_verga_m) * 4 * (1 + WASTE_REBAR)
    rebar_8mm_kg = rebar_8mm_m * 0.395  # kg/m para φ8mm

    # Estribos: φ5mm a cada 20cm
    n_estribos = math.ceil((total_canaleta_m + total_verga_m) / 0.20)
    perimetro_estribo = 2 * (block_w + CINTA_RESPALDO_ALTURA) + 0.20  # + dobras
    rebar_5mm_m = n_estribos * perimetro_estribo * (1 + WASTE_REBAR)
    rebar_5mm_kg = rebar_5mm_m * 0.154  # kg/m para φ5mm

    bom.append({
        "categoria": "Aço",
        "material": "Barra CA-50 φ8mm",
        "unidade": "kg",
        "quantidade": round(rebar_8mm_kg, 1),
        "observacao": "Cintas e vergas",
    })

    bom.append({
        "categoria": "Aço",
        "material": "Barra CA-60 φ5mm (estribos)",
        "unidade": "kg",
        "quantidade": round(rebar_5mm_kg, 1),
        "observacao": "Espaçamento: c/20cm",
    })

    # === FOUNDATION ===
    # Consolidate foundations by type and dimensions (avoid one entry per wall)
    if project.foundations:
        # Total structural wall length for sapata corrida volume
        total_struct_wall_length = 0.0
        for floor in project.floor_plans:
            for wall in floor.walls:
                if wall.is_structural:
                    total_struct_wall_length += wall.length_m

        # Group by (type, width, height)
        fund_groups = {}
        for foundation in project.foundations:
            key = (foundation.type.value, foundation.width_m, foundation.height_m)
            if key not in fund_groups:
                fund_groups[key] = foundation

        for key, foundation in fund_groups.items():
            if foundation.type == FoundationType.SAPATA_CORRIDA:
                vol_per_m = foundation.width_m * foundation.height_m
                vol_total = vol_per_m * total_struct_wall_length * (1 + WASTE_MORTAR)
                bom.append({
                    "categoria": "Fundação",
                    "material": f"Concreto fck ≥ 20 MPa (sapata corrida B={foundation.width_m:.2f}m)",
                    "unidade": "m³",
                    "quantidade": round(vol_total, 2),
                    "observacao": f"H={foundation.height_m:.2f}m, Prof.={foundation.depth_m:.2f}m, L={total_struct_wall_length:.1f}m",
                })
            elif foundation.type == FoundationType.RADIER:
                vol = foundation.width_m ** 2 * foundation.height_m * (1 + WASTE_MORTAR)
                bom.append({
                    "categoria": "Fundação",
                    "material": f"Concreto fck ≥ 20 MPa (radier {foundation.width_m:.1f}×{foundation.width_m:.1f}m)",
                    "unidade": "m³",
                    "quantidade": round(vol, 2),
                    "observacao": f"H={foundation.height_m:.2f}m, {foundation.rebar}",
                })

            bom.append({
                "categoria": "Fundação",
                "material": f"Armadura fundação ({foundation.rebar})",
                "unidade": "vb",
                "quantidade": 1,
                "observacao": "Conforme detalhamento",
            })

    return bom


def write_masonry_bom_csv(project: MasonryProject, output_path: str) -> str:
    """Escreve BOM de alvenaria em CSV.

    Args:
        project: Projeto de alvenaria completo
        output_path: Caminho do CSV

    Returns:
        Caminho do arquivo salvo
    """
    rows = calculate_masonry_bom(project)

    fieldnames = ["categoria", "material", "unidade", "quantidade", "observacao"]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"BOM alvenaria salva: {output_path}")
    return output_path
