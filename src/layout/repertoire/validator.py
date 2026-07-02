"""Validação de templates — circulação, privacidade, NBR 15575.

Valida templates TemplateV2 antes e depois da adaptação.
"""

import logging
from typing import List

from ._base import TemplateV2

logger = logging.getLogger(__name__)

# NBR 15575 — Áreas e dimensões mínimas
_MIN_AREA = {
    "bedroom": 9.0,   # 3×3m mínimo
    "living": 12.0,
    "kitchen": 4.0,
    "bathroom": 2.25,  # 1.5×1.5m mínimo funcional
    "service": 2.5,
    "circulation": 1.5,
    "garage": 12.0,
    "varanda": 2.0,
}

_MIN_DIM = {
    "bedroom": 3.00,   # quarto mínimo 3×3m
    "living": 2.40,
    "kitchen": 1.80,
    "bathroom": 1.20,  # mínimo funcional (ideal 1.5m)
    "service": 1.50,
    "circulation": 0.90,
    "garage": 3.00,
    "varanda": 1.00,
}


def validate_template(template: TemplateV2) -> List[str]:
    """Validação completa — retorna lista de problemas (vazia = OK)."""
    issues = []
    issues.extend(validate_nbr(template))
    issues.extend(validate_circulation(template))
    issues.extend(validate_privacy(template))
    return issues


def validate_nbr(template: TemplateV2) -> List[str]:
    """Valida áreas e dimensões mínimas por NBR 15575."""
    issues = []

    for room in template.rooms:
        zone = template.get_zone(room.zone_id)
        if zone is None:
            issues.append(f"{room.name}: zona '{room.zone_id}' não encontrada")
            continue

        w = room.rel_w * zone.width_m
        h = room.rel_h * zone.depth_m
        area = w * h
        min_side = min(w, h)

        if room.type in _MIN_AREA:
            min_a = _MIN_AREA[room.type]
            if area < min_a - 0.1:
                issues.append(
                    f"{room.name}: {area:.1f}m² < {min_a}m² mínimo"
                )

        if room.type in _MIN_DIM:
            min_d = _MIN_DIM[room.type]
            if min_side < min_d - 0.05:
                issues.append(
                    f"{room.name}: dimensão {min_side:.2f}m < {min_d}m mínimo"
                )

    return issues


def validate_circulation(template: TemplateV2) -> List[str]:
    """Valida grafo de circulação — BFS sem passar por quartos.

    Regras:
    - Todo cômodo deve ser acessível a partir da entrada
    - Serviço não deve ser acessível apenas via banheiro
    - Quartos não devem ser passagem para outros cômodos
    """
    issues = []
    circ = template.circulation

    # Identify bedroom rooms
    bedroom_names = {r.name for r in template.rooms if r.type == "bedroom"}

    # Identify en-suite bathrooms (bathroom reachable only via its bedroom)
    suite_bathrooms = set()
    for room in template.rooms:
        if room.type == "bathroom":
            # Check if this bathroom is only reachable from a bedroom (suite)
            parents = [src for src, dsts in circ.edges.items() if room.name in dsts]
            if all(p in bedroom_names for p in parents):
                suite_bathrooms.add(room.name)

    # BFS from entrance, only through non-bedrooms
    reachable_without_bedrooms = set()
    queue = [circ.entrance]
    reachable_without_bedrooms.add(circ.entrance)

    while queue:
        current = queue.pop(0)
        for neighbor in circ.edges.get(current, []):
            if neighbor not in reachable_without_bedrooms:
                reachable_without_bedrooms.add(neighbor)
                # Can enter bedrooms (they're destinations), but don't traverse them
                if neighbor not in bedroom_names:
                    queue.append(neighbor)

    # Check all rooms are reachable (suite bathrooms exempt — they're private)
    all_rooms = circ.all_rooms()
    for room_name in all_rooms:
        if room_name in suite_bathrooms:
            continue  # en-suite bathroom is correctly private
        if room_name not in reachable_without_bedrooms:
            issues.append(
                f"Circulação: {room_name} inacessível sem passar por quarto"
            )

    # Check service is not only reachable through bathroom
    service_rooms = [r.name for r in template.rooms if r.type == "service"]
    bathroom_names = {r.name for r in template.rooms if r.type == "bathroom"}

    for svc in service_rooms:
        # BFS excluding bathrooms
        reachable_no_bath = set()
        q = [circ.entrance]
        reachable_no_bath.add(circ.entrance)
        while q:
            c = q.pop(0)
            for n in circ.edges.get(c, []):
                if n not in reachable_no_bath and n not in bathroom_names:
                    reachable_no_bath.add(n)
                    if n not in bedroom_names:
                        q.append(n)
        if svc not in reachable_no_bath:
            issues.append(
                f"Circulação: {svc} só acessível via banheiro — "
                f"deve ter acesso direto pela cozinha/sala"
            )

    return issues


def validate_privacy(template: TemplateV2) -> List[str]:
    """Valida gradiente de privacidade.

    Regras:
    - Quartos devem estar na zona mais distante da rua (maior Y)
    - Sala deve estar na zona mais próxima da rua (menor Y)
    """
    issues = []

    if not template.privacy_gradient:
        return issues

    # Check that bedrooms are after living in the gradient
    bedroom_idxs = []
    living_idx = -1
    for i, room_name in enumerate(template.privacy_gradient):
        room = next((r for r in template.rooms if r.name == room_name), None)
        if room and room.type == "bedroom":
            bedroom_idxs.append(i)
        if room and room.type == "living":
            living_idx = i

    if living_idx >= 0 and bedroom_idxs:
        for bi in bedroom_idxs:
            if bi < living_idx:
                issues.append(
                    "Privacidade: quarto antes da sala no gradiente"
                )

    # Check physical position: bedrooms should be at higher Y than living
    living_rooms = [r for r in template.rooms if r.type == "living"]
    bedroom_rooms = [r for r in template.rooms if r.type == "bedroom"]

    if living_rooms and bedroom_rooms:
        living_max_y = max(
            template.get_zone(r.zone_id).anchor_y + r.rel_y * template.get_zone(r.zone_id).depth_m
            for r in living_rooms
            if template.get_zone(r.zone_id)
        )
        bedroom_min_y = min(
            template.get_zone(r.zone_id).anchor_y + r.rel_y * template.get_zone(r.zone_id).depth_m
            for r in bedroom_rooms
            if template.get_zone(r.zone_id)
        )

        if bedroom_min_y < living_max_y - 0.5:
            issues.append(
                "Privacidade: quartos mais próximos da rua que a sala"
            )

    return issues


def validate_lot_fit(
    template: TemplateV2,
    lot_width: float,
    lot_depth: float,
) -> List[str]:
    """Valida se o template cabe no lote com recuos."""
    issues = []
    lp = template.lot_placement

    bb = template.bounding_box
    bb_w = bb[2] - bb[0]
    bb_h = bb[3] - bb[1]

    avail_w = lot_width - 2 * lp.setback_side_m
    avail_d = lot_depth - lp.setback_front_m - lp.setback_back_m

    if bb_w > avail_w + 0.1:
        issues.append(
            f"Largura {bb_w:.1f}m > disponível {avail_w:.1f}m "
            f"(lote {lot_width}m - 2×{lp.setback_side_m}m recuo)"
        )

    if bb_h > avail_d + 0.1:
        issues.append(
            f"Profundidade {bb_h:.1f}m > disponível {avail_d:.1f}m "
            f"(lote {lot_depth}m - {lp.setback_front_m}+{lp.setback_back_m}m recuos)"
        )

    # Coverage check
    max_built = lot_width * lot_depth * lp.building_coverage_max
    if template.built_area_m2 > max_built + 0.5:
        issues.append(
            f"Área construída {template.built_area_m2:.1f}m² > "
            f"máximo {max_built:.1f}m² (taxa {lp.building_coverage_max:.0%})"
        )

    return issues
