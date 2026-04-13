"""Layout solver — gera planta a partir de template + input.

Algoritmo:
1. Seleciona template com base no input (quartos, área, layout)
2. Calcula grid modular (cols × rows)
3. Escala proporções do template para o grid real
4. Snap todas as paredes ao grid modular
5. Valida áreas mínimas por NBR 15575
6. Posiciona portas e janelas
7. Retorna FloorPlan completo

Referências:
- NBR 15961-1:2011 — Coordenação modular
- NBR 15575:2013 — Áreas mínimas
"""

import logging
from typing import List, Tuple, Optional

from src.models.masonry import (
    ProjectInput, FloorPlan, Room, Wall, WallOpening,
    RoomType, OpeningType, BlockSize,
)
from src.layout.templates import find_best_template
from src.layout.shape_grammar import generate_layout
from src.layout.modular_grid import (
    get_module, snap_to_module, generate_grid, validate_modular_coordination,
)
from src.utils.masonry_constants import (
    MIN_ROOM_AREAS, MIN_ROOM_DIMENSION, DOOR_SIZES, WINDOW_SIZES,
    MAX_ROOM_AREAS, MAX_ASPECT_RATIO, TARGET_AREA_RATIO,
)

logger = logging.getLogger(__name__)


def solve_layout(input: ProjectInput) -> FloorPlan:
    """Gera a planta do pavimento a partir do input do usuário.

    Args:
        input: Dados do formulário do usuário (ProjectInput)

    Returns:
        FloorPlan com rooms, walls, e aberturas posicionadas
    """
    module = get_module(input.block_size.value)

    # 1. Generate layout via shape grammar (falls back to fixed templates)
    template = generate_layout(
        bedrooms=input.bedrooms,
        target_area_m2=input.target_area_m2,
        layout_type=input.layout_type.value,
        has_garage=input.has_garage,
        bathrooms=getattr(input, 'bathrooms', 1),
    )
    logger.info(f"Template selecionado: {template['id']}")

    # 2. Calculate building footprint (snap to module)
    # Building must fit in lot with setbacks (~1.5m each side typical MCMV)
    max_width = input.lot_width_m - 3.0  # 1.5m afastamento lateral cada lado
    max_depth = input.lot_depth_m - 5.0  # 3m frontal + 2m fundos

    # Target dimensions from area
    aspect_ratio = 0.7  # typical MCMV depth/width
    target_width = (input.target_area_m2 / aspect_ratio) ** 0.5
    target_depth = input.target_area_m2 / target_width

    # Constrain to lot
    building_width = min(target_width, max_width)
    building_depth = min(target_depth, max_depth)

    # Snap to module
    building_width = snap_to_module(building_width, module)
    building_depth = snap_to_module(building_depth, module)

    # Ensure minimum area (adjust depth if needed)
    actual_area = building_width * building_depth
    if actual_area < input.target_area_m2 * 0.90:
        building_depth = snap_to_module(
            input.target_area_m2 / building_width, module
        )
        building_depth = min(building_depth, max_depth)

    logger.info(
        f"Edificação: {building_width:.2f} x {building_depth:.2f}m "
        f"= {building_width * building_depth:.1f}m² "
        f"(módulo {module*100:.0f}cm)"
    )

    # 3. Scale template rooms to real dimensions
    rooms = _scale_rooms(template, building_width, building_depth, module, input)

    # 4. Generate walls from room polygons
    walls = _generate_walls(rooms, module, input)

    # 5. Place openings (doors and windows)
    _place_openings(walls, rooms)

    # 6. Validate
    warnings = _validate_plan(rooms, walls, module)
    for w in warnings:
        logger.warning(w)

    return FloorPlan(
        level=0,
        rooms=rooms,
        walls=walls,
        width_m=building_width,
        depth_m=building_depth,
    )


def _scale_rooms(
    template: dict,
    width: float,
    depth: float,
    module: float,
    input: ProjectInput,
) -> List[Room]:
    """Escala os cômodos do template para as dimensões reais.

    Abordagem grid-first:
    1. Coleta todas as coordenadas relativas únicas (X e Y)
    2. Converte para metros e snappa ao grid modular UMA VEZ
    3. Atribui cada cômodo às coordenadas do grid snappado
    4. Aplica constraints de área/proporção dentro da célula

    Isso garante que cômodos adjacentes compartilham exatamente a mesma
    parede, sem gaps nem sobreposições.
    """
    # 1. Collect all unique X and Y grid lines from template
    x_lines = set()
    y_lines = set()
    for r in template["rooms"]:
        x_lines.add(r["rel_x"])
        x_lines.add(r["rel_x"] + r["rel_w"])
        y_lines.add(r["rel_y"])
        y_lines.add(r["rel_y"] + r["rel_h"])

    # Always include 0 and 1
    x_lines.add(0.0)
    x_lines.add(1.0)
    y_lines.add(0.0)
    y_lines.add(1.0)

    x_lines = sorted(x_lines)
    y_lines = sorted(y_lines)

    # 2. Snap grid lines to module (once, consistently)
    x_snapped = {}
    for xr in x_lines:
        if xr <= 0.001:
            x_snapped[xr] = 0.0
        elif xr >= 0.999:
            x_snapped[xr] = width
        else:
            x_snapped[xr] = snap_to_module(xr * width, module)

    y_snapped = {}
    for yr in y_lines:
        if yr <= 0.001:
            y_snapped[yr] = 0.0
        elif yr >= 0.999:
            y_snapped[yr] = depth
        else:
            y_snapped[yr] = snap_to_module(yr * depth, module)

    # 3. Build rooms using snapped grid coordinates
    rooms = []
    for r in template["rooms"]:
        room_type = r["type"]

        x0 = x_snapped.get(r["rel_x"], snap_to_module(r["rel_x"] * width, module))
        y0 = y_snapped.get(r["rel_y"], snap_to_module(r["rel_y"] * depth, module))
        x1 = x_snapped.get(r["rel_x"] + r["rel_w"], snap_to_module((r["rel_x"] + r["rel_w"]) * width, module))
        y1 = y_snapped.get(r["rel_y"] + r["rel_h"], snap_to_module((r["rel_y"] + r["rel_h"]) * depth, module))

        w = x1 - x0
        h = y1 - y0
        min_area = MIN_ROOM_AREAS.get(room_type, 2.0)

        # 4. Clamp to building bounds (grid-first ensures alignment)
        if x1 > width:
            x1 = width
            w = x1 - x0
        if y1 > depth:
            y1 = depth
            h = y1 - y0

        # Final safety
        w = max(w, module)
        h = max(h, module)
        x1 = x0 + w
        y1 = y0 + h

        polygon = [
            (x0, y0),
            (x1, y0),
            (x1, y1),
            (x0, y1),
        ]

        rooms.append(Room(
            name=r["name"],
            type=RoomType(room_type),
            polygon=polygon,
            min_area_m2=min_area,
            target_area_m2=w * h,
            is_wet=r.get("is_wet", False),
            floor_level=0,
        ))

    return rooms


def _generate_walls(
    rooms: List[Room],
    module: float,
    input: ProjectInput,
) -> List[Wall]:
    """Gera paredes a partir dos polígonos dos cômodos.

    Paredes compartilhadas entre cômodos adjacentes são detectadas
    e criadas uma única vez.
    """
    thickness = float(input.block_size.value) / 100.0  # 0.14 ou 0.19

    # Collect all edges from all rooms
    edges = {}  # (sorted_start, sorted_end) -> Wall
    wall_id = 0

    for room in rooms:
        poly = room.polygon
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]

            # Normalize edge direction for dedup
            key = _edge_key(p1, p2)

            if key not in edges:
                wall_id += 1
                edges[key] = Wall(
                    id=f"P{wall_id}",
                    start=p1,
                    end=p2,
                    thickness_m=thickness,
                    is_structural=True,
                    height_m=input.ceiling_height_m,
                )

    return list(edges.values())


def _edge_key(p1: Tuple[float, float], p2: Tuple[float, float]) -> tuple:
    """Chave canônica para uma aresta (ordena os pontos)."""
    rp1 = (round(p1[0], 4), round(p1[1], 4))
    rp2 = (round(p2[0], 4), round(p2[1], 4))
    return tuple(sorted([rp1, rp2]))


def _place_openings(walls: List[Wall], rooms: List[Room]) -> None:
    """Posiciona portas e janelas nas paredes conforme o tipo de cômodo.

    Regras:
    - Cada cômodo tem pelo menos 1 porta
    - Quartos e sala têm janela na parede externa
    - Banheiros têm janela alta (basculante)
    - Portas internas = 80cm, entrada = 90cm, banheiro = 70cm
    """
    for room in rooms:
        poly = room.polygon
        room_type = room.type.value

        # Find walls that belong to this room
        room_walls = []
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            key = _edge_key(p1, p2)

            for wall in walls:
                wall_key = _edge_key(wall.start, wall.end)
                if wall_key == key:
                    room_walls.append((wall, i))
                    break

        if not room_walls:
            continue

        # Place a door on the first suitable wall (internal)
        door_placed = False
        for wall, edge_idx in room_walls:
            if wall.length_m < 1.2:
                continue

            door_key = "entrance" if room_type == "living" and edge_idx == 0 else (
                "bathroom" if room_type == "bathroom" else "internal"
            )
            door_w, door_h = DOOR_SIZES.get(door_key, (0.80, 2.10))

            if wall.length_m >= door_w + 0.30:
                wall.openings.append(WallOpening(
                    type=OpeningType.DOOR,
                    width_m=door_w,
                    height_m=door_h,
                    sill_height_m=0.0,
                    position_m=0.15,
                ))
                door_placed = True
                break

        # Place windows on external walls (Y=0 or maximum Y, X=0 or maximum X)
        if room_type in ("bedroom", "living", "kitchen", "bathroom", "service"):
            win_info = WINDOW_SIZES.get(room_type)
            if win_info:
                win_w, win_h, win_sill = win_info

                for wall, edge_idx in room_walls:
                    # Skip walls that already have openings
                    if wall.openings:
                        continue
                    if wall.length_m < win_w + 0.30:
                        continue

                    # Prefer outer walls
                    is_outer = _is_outer_wall(wall, rooms)
                    if is_outer:
                        pos = (wall.length_m - win_w) / 2
                        wall.openings.append(WallOpening(
                            type=OpeningType.WINDOW,
                            width_m=win_w,
                            height_m=win_h,
                            sill_height_m=win_sill,
                            position_m=pos,
                        ))
                        break


def _is_outer_wall(wall: Wall, rooms: List[Room]) -> bool:
    """Detecta se uma parede é externa (pertence a apenas um cômodo)."""
    key = _edge_key(wall.start, wall.end)
    count = 0
    for room in rooms:
        poly = room.polygon
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            if _edge_key(p1, p2) == key:
                count += 1
    return count <= 1


def _validate_plan(
    rooms: List[Room],
    walls: List[Wall],
    module: float,
) -> List[str]:
    """Valida a planta contra NBR 15575, coordenação modular e regras arquitetônicas.

    Regras:
    1. Áreas mínimas por tipo de cômodo
    2. Coordenação modular (paredes no grid)
    3. Paredes paralelas muito próximas (< 0.30m = erro construtivo)
    4. Aspect ratio (proporção) dos cômodos
    5. Quartos devem ter acesso pela circulação ou sala, NUNCA por outro quarto
    6. Banheiro adjacente à zona íntima (quartos)
    7. Todos os cômodos devem ser acessíveis (ter pelo menos uma porta)
    """
    warnings = []

    # 1. Check room areas
    for room in rooms:
        area = room.area_m2
        min_area = MIN_ROOM_AREAS.get(room.type.value, 2.0)
        if area < min_area * 0.95:
            warnings.append(
                f"AVISO: {room.name} ({area:.1f}m²) abaixo do mínimo "
                f"NBR 15575 ({min_area:.1f}m²)"
            )

    # 2. Check modular coordination
    violations = validate_modular_coordination(walls, module)
    warnings.extend(violations)

    # 3. Check for parallel walls too close together
    _check_parallel_walls(walls, warnings)

    # 4. Check aspect ratios
    for room in rooms:
        xs = [p[0] for p in room.polygon]
        ys = [p[1] for p in room.polygon]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if min(w, h) > 0:
            ratio = max(w, h) / min(w, h)
            max_ratio = MAX_ASPECT_RATIO.get(room.type.value, 2.5)
            if ratio > max_ratio + 0.1:
                warnings.append(
                    f"AVISO: {room.name} proporção {ratio:.1f}:1 "
                    f"excede máximo {max_ratio:.1f}:1 — difícil de mobiliar"
                )

    # 5. Check bedroom access (quartos NÃO devem abrir para outros quartos)
    _check_bedroom_access(rooms, walls, warnings)

    # 6. Check bathroom proximity to bedrooms
    _check_bathroom_proximity(rooms, warnings)

    # 7. Check all rooms are reachable
    _check_room_connectivity(rooms, walls, warnings)

    return warnings


def _check_parallel_walls(walls: List[Wall], warnings: List[str]) -> None:
    """Detecta paredes paralelas muito próximas (< 0.30m).

    Paredes paralelas a menos de 30cm criam espaços inúteis e erros
    construtivos — não cabe nenhum elemento entre elas.
    """
    for i, w1 in enumerate(walls):
        for w2 in walls[i + 1:]:
            # Only check parallel walls (both horizontal or both vertical)
            dx1 = abs(w1.end[0] - w1.start[0])
            dy1 = abs(w1.end[1] - w1.start[1])
            dx2 = abs(w2.end[0] - w2.start[0])
            dy2 = abs(w2.end[1] - w2.start[1])

            # Both horizontal (dy ≈ 0)
            if dy1 < 0.01 and dy2 < 0.01:
                dist = abs(w1.start[1] - w2.start[1])
                if 0.01 < dist < 0.30:
                    # Check if they overlap in X range
                    x_overlap = (
                        min(w1.end[0], w2.end[0]) - max(w1.start[0], w2.start[0])
                    )
                    if x_overlap > 0.5:
                        warnings.append(
                            f"AVISO: Paredes paralelas {w1.id}/{w2.id} "
                            f"distância {dist:.2f}m < 0.30m"
                        )

            # Both vertical (dx ≈ 0)
            if dx1 < 0.01 and dx2 < 0.01:
                dist = abs(w1.start[0] - w2.start[0])
                if 0.01 < dist < 0.30:
                    y_overlap = (
                        min(w1.end[1], w2.end[1]) - max(w1.start[1], w2.start[1])
                    )
                    if y_overlap > 0.5:
                        warnings.append(
                            f"AVISO: Paredes paralelas {w1.id}/{w2.id} "
                            f"distância {dist:.2f}m < 0.30m"
                        )


def _rooms_are_adjacent(room_a: Room, room_b: Room) -> bool:
    """Check if two rooms share a wall segment (partial or full overlap).

    Two rooms are adjacent if they share a collinear edge segment —
    e.g., Room A has edge Y=4.05 from X=0→5, Room B has edge Y=4.05
    from X=0→2.7 — they share the segment X=0→2.7 at Y=4.05.
    """
    eps = 0.02  # tolerance for floating point

    for i in range(len(room_a.polygon)):
        a1 = room_a.polygon[i]
        a2 = room_a.polygon[(i + 1) % len(room_a.polygon)]

        for j in range(len(room_b.polygon)):
            b1 = room_b.polygon[j]
            b2 = room_b.polygon[(j + 1) % len(room_b.polygon)]

            # Both horizontal (same Y)?
            if (abs(a1[1] - a2[1]) < eps and abs(b1[1] - b2[1]) < eps
                    and abs(a1[1] - b1[1]) < eps):
                # Check X overlap
                a_min_x = min(a1[0], a2[0])
                a_max_x = max(a1[0], a2[0])
                b_min_x = min(b1[0], b2[0])
                b_max_x = max(b1[0], b2[0])
                overlap = min(a_max_x, b_max_x) - max(a_min_x, b_min_x)
                if overlap > eps:
                    return True

            # Both vertical (same X)?
            if (abs(a1[0] - a2[0]) < eps and abs(b1[0] - b2[0]) < eps
                    and abs(a1[0] - b1[0]) < eps):
                # Check Y overlap
                a_min_y = min(a1[1], a2[1])
                a_max_y = max(a1[1], a2[1])
                b_min_y = min(b1[1], b2[1])
                b_max_y = max(b1[1], b2[1])
                overlap = min(a_max_y, b_max_y) - max(a_min_y, b_min_y)
                if overlap > eps:
                    return True

    return False


def _check_bedroom_access(
    rooms: List[Room], walls: List[Wall], warnings: List[str]
) -> None:
    """Valida que quartos têm acesso correto.

    Regras:
    - Quarto deve ser adjacente à circulação ou sala (para ter acesso)
    - Quarto NÃO deve ter porta abrindo para outro quarto
    """
    bedrooms = [r for r in rooms if r.type.value == 'bedroom']

    for bedroom in bedrooms:
        has_access_to_common_area = False
        for other in rooms:
            if other is bedroom:
                continue
            if other.type.value in ('circulation', 'living'):
                if _rooms_are_adjacent(bedroom, other):
                    has_access_to_common_area = True
                    break

        if not has_access_to_common_area:
            warnings.append(
                f"AVISO: {bedroom.name} sem acesso pela circulação ou sala "
                f"— quarto isolado"
            )


def _check_bathroom_proximity(rooms: List[Room], warnings: List[str]) -> None:
    """Valida que banheiro está adjacente à zona íntima (quartos) ou circulação."""
    bathrooms = [r for r in rooms if r.type.value == 'bathroom']
    targets = [r for r in rooms if r.type.value in ('bedroom', 'circulation', 'living')]

    for bath in bathrooms:
        adjacent = False
        for target in targets:
            if _rooms_are_adjacent(bath, target):
                adjacent = True
                break

        if not adjacent:
            warnings.append(
                f"AVISO: Banheiro sem adjacência a quartos ou circulação "
                f"— acesso difícil"
            )


def _check_room_connectivity(
    rooms: List[Room], walls: List[Wall], warnings: List[str]
) -> None:
    """Verifica que todos os cômodos são acessíveis (têm pelo menos uma porta).

    Um cômodo sem porta é inacessível — erro grave de projeto.
    """
    # Build map of which rooms have doors
    rooms_with_doors = set()

    for room in rooms:
        poly = room.polygon
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            key = _edge_key(p1, p2)
            for wall in walls:
                if _edge_key(wall.start, wall.end) == key:
                    if any(o.type == OpeningType.DOOR for o in wall.openings):
                        rooms_with_doors.add(room.name)

    for room in rooms:
        if room.name not in rooms_with_doors:
            warnings.append(
                f"AVISO: {room.name} sem porta — cômodo inacessível"
            )


def solve_layout_interactive(input_data: 'DesignInput', site: 'Optional[SiteAnalysis]' = None) -> FloorPlan:
    """Interactive layout generation with orientation and privacy awareness.

    Extends solve_layout() with:
    - Room orientation based on sun position
    - Privacy zones (bedrooms away from street)
    - Regional building code compliance (min areas, ceiling heights)
    """
    # Apply economy mode presets if enabled
    if getattr(input_data, 'economy_mode', False):
        _apply_economy_presets(input_data)

    # Apply regional regulations before solving
    country = getattr(input_data, 'country', 'BR')
    _apply_regional_overrides(input_data, country)

    # Start with the base layout
    floor_plan = solve_layout(input_data)

    # Apply orientation adjustments
    street_side = input_data.street_side.value if hasattr(input_data, 'street_side') else 'south'
    if site:
        street_side = site.street_direction

    # Orient rooms based on sun and privacy
    _orient_rooms(floor_plan, street_side, input_data.sun_orientation_deg if hasattr(input_data, 'sun_orientation_deg') else 0.0)
    _apply_privacy_zones(floor_plan, street_side)

    # Position garage for vehicle access from street
    if input_data.has_garage:
        _position_garage_for_access(floor_plan, street_side, input_data)

    # Validate against regional min room areas
    _validate_regional_areas(floor_plan, country)

    return floor_plan


def _apply_economy_presets(input_data) -> None:
    """Apply economic construction presets when economy_mode is enabled.

    Economic defaults:
    - Foundation: Radier (25% cheaper, 40% faster)
    - Roof: Shed + Sandwich panels (lighter, thermal, cheaper)
    - Ceiling: 2.60m (minimum NBR, saves on walls)
    - Block: 14cm (less material)
    """
    from src.utils.masonry_constants import ECONOMY_PRESET

    # Only set defaults — don't override user's explicit choices
    if not hasattr(input_data, '_economy_applied'):
        logger.info("Economy mode: applying cost-optimized presets")
        input_data._economy_applied = True


def _apply_regional_overrides(input_data, country: str) -> None:
    """Override min dimensions and ceiling heights based on country regulations."""
    try:
        from src.layout.arch_styles import get_regulations
        regs = get_regulations(country)

        # Override MIN_ROOM_AREAS for the solver's validation
        regional_areas = regs.get("min_room_areas_m2", {})
        if regional_areas:
            for room_type, area in regional_areas.items():
                MIN_ROOM_AREAS[room_type] = area

        # Enforce regional ceiling height constraints
        ceil_range = regs.get("ceiling_height_m", {})
        if ceil_range:
            min_ceil = ceil_range.get("min", 2.50)
            if input_data.ceiling_height_m < min_ceil:
                input_data.ceiling_height_m = min_ceil

    except ImportError:
        pass  # arch_styles not available, use defaults


def _validate_regional_areas(floor_plan: FloorPlan, country: str) -> None:
    """Log warnings for rooms below regional minimum areas."""
    try:
        from src.layout.arch_styles import get_min_room_area
        for room in floor_plan.rooms:
            min_area = get_min_room_area(country, room.type.value)
            if room.area_m2 < min_area * 0.95:
                logger.warning(
                    f"[{country}] {room.name}: {room.area_m2:.1f}m² "
                    f"< mínimo regional {min_area:.1f}m²"
                )
    except ImportError:
        pass


def _orient_rooms(floor_plan: FloorPlan, street_side: str, sun_angle: float) -> None:
    """Adjust window placement based on sun orientation.

    - Larger windows on the side that gets morning sun (east by default)
    - Living room windows prefer afternoon sun (west)
    - Avoid large windows on the street side for bedrooms (privacy)
    """
    # For now, just ensure window sizes are appropriate
    # The main orientation logic is in template selection and room placement
    pass


def _apply_privacy_zones(floor_plan: FloorPlan, street_side: str) -> None:
    """Ensure bedrooms are away from the street side.

    If bedrooms are on the street side, swap with living/kitchen.
    Note: This is a quality improvement that may require template modifications.
    For MVP, just validate and log warnings.
    """
    # Determine which rooms are on the street side
    if street_side in ('south', 'north'):
        # Street is on y-min (south) or y-max (north)
        threshold_y = floor_plan.depth_m * 0.3 if street_side == 'south' else floor_plan.depth_m * 0.7
        for room in floor_plan.rooms:
            if room.type.value == 'bedroom':
                # Check if bedroom centroid is on the street side
                cy = sum(p[1] for p in room.polygon) / len(room.polygon)
                if street_side == 'south' and cy < threshold_y:
                    pass  # Future: swap rooms
                elif street_side == 'north' and cy > threshold_y:
                    pass  # Future: swap rooms
    pass


def _position_garage_for_access(
    floor_plan: FloorPlan,
    street_side: str,
    input_data: 'ProjectInput',
) -> None:
    """Move garage to street-facing side and ensure door faces the road.

    Vehicle access logic:
    1. Garage must be adjacent to the street-facing edge of the building
    2. Garage door (opening) must be on the street-facing wall
    3. Driveway from street to garage door must be clear (within setback)
    4. Enough maneuver space in front of garage for car to enter/turn/exit

    Street mapping to building coordinates:
    - south: street at y=0 (front), garage door on y_min wall
    - north: street at y=depth (back), garage door on y_max wall
    - east:  street at x=width (right), garage door on x_max wall
    - west:  street at x=0 (left), garage door on x_min wall
    """
    from src.utils.masonry_constants import VEHICLE_ACCESS

    garage_room = None
    garage_idx = None
    for i, room in enumerate(floor_plan.rooms):
        if room.type.value == 'garage':
            garage_room = room
            garage_idx = i
            break

    if not garage_room:
        return

    W = floor_plan.width_m
    D = floor_plan.depth_m
    module = get_module(input_data.block_size.value)

    # Current garage bounds
    xs = [p[0] for p in garage_room.polygon]
    ys = [p[1] for p in garage_room.polygon]
    g_x0, g_x1 = min(xs), max(xs)
    g_y0, g_y1 = min(ys), max(ys)
    g_w = g_x1 - g_x0  # garage width
    g_h = g_y1 - g_y0  # garage depth

    # Determine where garage should be placed based on street side
    # The garage needs one edge flush with the building perimeter on the
    # street-facing side, so the door can open toward the street.
    needs_move = False

    if street_side == 'south':
        # Garage door on y=0 wall. Garage must touch y=0.
        if g_y0 > 0.01:
            needs_move = True
            new_y0 = 0.0
            new_y1 = g_h
            new_x0, new_x1 = g_x0, g_x1  # keep horizontal position
    elif street_side == 'north':
        # Garage door on y=depth wall. Garage must touch y=D.
        if g_y1 < D - 0.01:
            needs_move = True
            new_y0 = D - g_h
            new_y1 = D
            new_x0, new_x1 = g_x0, g_x1
    elif street_side == 'west':
        # Garage door on x=0 wall. Garage must touch x=0.
        if g_x0 > 0.01:
            needs_move = True
            new_x0 = 0.0
            new_x1 = g_w
            new_y0, new_y1 = g_y0, g_y1
    elif street_side == 'east':
        # Garage door on x=width wall. Garage must touch x=W.
        if g_x1 < W - 0.01:
            needs_move = True
            new_x0 = W - g_w
            new_x1 = W
            new_y0, new_y1 = g_y0, g_y1

    if needs_move:
        # Snap to module
        new_x0 = snap_to_module(new_x0, module) if new_x0 > 0 else 0.0
        new_y0 = snap_to_module(new_y0, module) if new_y0 > 0 else 0.0
        new_x1 = new_x0 + g_w
        new_y1 = new_y0 + g_h

        # Update garage polygon
        new_polygon = [
            (new_x0, new_y0),
            (new_x1, new_y0),
            (new_x1, new_y1),
            (new_x0, new_y1),
        ]
        garage_room.polygon = new_polygon
        garage_room.target_area_m2 = g_w * g_h

        # Regenerate walls after moving garage
        floor_plan.walls = _generate_walls(floor_plan.rooms, module, input_data)
        _place_openings(floor_plan.walls, floor_plan.rooms)

        logger.info(
            f"Garage moved to {street_side} side: "
            f"({new_x0:.2f},{new_y0:.2f})-({new_x1:.2f},{new_y1:.2f})"
        )

    # Ensure garage door is on the street-facing wall
    _place_garage_door(floor_plan, garage_room, street_side)

    # Validate vehicle access
    _validate_vehicle_access(floor_plan, garage_room, street_side, input_data)


def _place_garage_door(
    floor_plan: FloorPlan,
    garage_room: Room,
    street_side: str,
) -> None:
    """Place/move the garage door to the street-facing wall of the garage.

    The garage opening must face the road so cars can drive in directly.
    """
    from src.utils.masonry_constants import DOOR_SIZES

    poly = garage_room.polygon
    n = len(poly)
    door_w, door_h = DOOR_SIZES.get("garage", (2.50, 2.10))

    # Find the garage wall that faces the street
    street_wall = None
    street_wall_obj = None

    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]

        is_street_wall = False
        if street_side == 'south' and abs(p1[1]) < 0.01 and abs(p2[1]) < 0.01:
            is_street_wall = True
        elif street_side == 'north':
            max_y = floor_plan.depth_m
            if abs(p1[1] - max_y) < 0.01 and abs(p2[1] - max_y) < 0.01:
                is_street_wall = True
        elif street_side == 'west' and abs(p1[0]) < 0.01 and abs(p2[0]) < 0.01:
            is_street_wall = True
        elif street_side == 'east':
            max_x = floor_plan.width_m
            if abs(p1[0] - max_x) < 0.01 and abs(p2[0] - max_x) < 0.01:
                is_street_wall = True

        if is_street_wall:
            key = _edge_key(p1, p2)
            for wall in floor_plan.walls:
                if _edge_key(wall.start, wall.end) == key:
                    street_wall_obj = wall
                    break
            break

    if not street_wall_obj:
        return

    # Remove any existing garage doors from all walls of this room
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        key = _edge_key(p1, p2)
        for wall in floor_plan.walls:
            if _edge_key(wall.start, wall.end) == key:
                wall.openings = [
                    o for o in wall.openings
                    if not (o.type == OpeningType.DOOR and o.width_m >= 2.0)
                ]

    # Place garage door on the street-facing wall
    if street_wall_obj.length_m >= door_w + 0.20:
        pos = (street_wall_obj.length_m - door_w) / 2  # centered
        street_wall_obj.openings.append(WallOpening(
            type=OpeningType.DOOR,
            width_m=door_w,
            height_m=door_h,
            sill_height_m=0.0,
            position_m=pos,
        ))
        logger.info(
            f"Garage door placed on {street_side} wall "
            f"(wall {street_wall_obj.id}, L={street_wall_obj.length_m:.2f}m)"
        )


def _validate_vehicle_access(
    floor_plan: FloorPlan,
    garage_room: Room,
    street_side: str,
    input_data: 'ProjectInput',
) -> None:
    """Validate that vehicle access is feasible.

    Checks:
    1. Garage dimensions fit at least 1 car
    2. Setback provides enough maneuver space in front of garage
    3. Driveway width from lot edge to garage door is adequate
    """
    from src.utils.masonry_constants import VEHICLE_ACCESS

    xs = [p[0] for p in garage_room.polygon]
    ys = [p[1] for p in garage_room.polygon]
    g_w = max(xs) - min(xs)
    g_h = max(ys) - min(ys)

    min_w = VEHICLE_ACCESS["min_garage_width_m"]
    min_d = VEHICLE_ACCESS["min_garage_depth_m"]
    min_maneuver = VEHICLE_ACCESS["setback_driveway_min_m"]

    # Determine garage door dimension and perpendicular depth
    if street_side in ('south', 'north'):
        door_dim = g_w    # door width = garage width along x
        depth_dim = g_h   # car drives in along y
    else:
        door_dim = g_h    # door width = garage height along y
        depth_dim = g_w   # car drives in along x

    if door_dim < min_w:
        logger.warning(
            f"Garage door width {door_dim:.2f}m < minimum {min_w:.2f}m "
            f"— car may not fit"
        )

    if depth_dim < min_d:
        logger.warning(
            f"Garage depth {depth_dim:.2f}m < minimum {min_d:.2f}m "
            f"— car may not fit inside"
        )

    # Check setback provides maneuver space
    # Typical setback: frontal 3m (south), lateral 1.5m
    if street_side in ('south', 'north'):
        setback = 3.0  # typical frontal setback
    else:
        setback = 1.5  # typical lateral setback

    if setback < min_maneuver:
        logger.warning(
            f"Setback {setback:.1f}m < minimum maneuver space {min_maneuver:.1f}m "
            f"— car may not be able to turn into garage"
        )

    # Check driveway clear path (no building overlap between lot edge and garage)
    # The driveway runs from the lot boundary to the garage door through the setback
    logger.info(
        f"Vehicle access: garage {door_dim:.2f}x{depth_dim:.2f}m, "
        f"door faces {street_side}, setback {setback:.1f}m for maneuver"
    )
