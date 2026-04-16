"""Repertório arquitetônico — biblioteca de plantas residenciais.

Sistema de templates v2 baseado em zonas compostas. Substitui a geração
puramente matemática por um repertório de soluções arquitetônicas
comprovadas que são adaptadas aos parâmetros do usuário.

Uso:
    from src.layout.repertoire import get_all_templates, select_and_adapt

    # Listar templates compatíveis
    templates = get_all_templates(bedrooms=2)

    # Selecionar e adaptar ao input do usuário
    legacy_dict = select_and_adapt(project_input)
"""

import logging
from typing import List, Optional, Dict, Any

from ._base import TemplateV2
from .compat import to_legacy_template

logger = logging.getLogger(__name__)

# Registry — lazy-loaded
_registry: Optional[List[TemplateV2]] = None


def _load_registry() -> List[TemplateV2]:
    """Carrega todos os templates de todos os catálogos."""
    global _registry
    if _registry is not None:
        return _registry

    templates = []

    try:
        from .catalog_2q import _templates as t2q
        templates.extend(t2q())
    except Exception as e:
        logger.warning(f"Failed to load catalog_2q: {e}")

    try:
        from .catalog_1q import _templates as t1q
        templates.extend(t1q())
    except ImportError:
        pass  # catalog not yet created
    except Exception as e:
        logger.warning(f"Failed to load catalog_1q: {e}")

    try:
        from .catalog_3q import _templates as t3q
        templates.extend(t3q())
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to load catalog_3q: {e}")

    _registry = templates
    logger.info(f"Repertoire loaded: {len(templates)} templates")
    return _registry


def get_all_templates(bedrooms: Optional[int] = None) -> List[TemplateV2]:
    """Retorna todos os templates, opcionalmente filtrados por quartos."""
    templates = _load_registry()
    if bedrooms is not None:
        templates = [t for t in templates if t.bedrooms == bedrooms]
    return templates


def select_and_adapt(input_data) -> Optional[Dict[str, Any]]:
    """Seleciona o melhor template e adapta ao input.

    Retorna dict legado compatível com solver._scale_rooms(),
    ou None se nenhum template é adequado.
    """
    bedrooms = getattr(input_data, 'bedrooms', None)
    target_area = getattr(input_data, 'target_area_m2', None)
    has_garage = getattr(input_data, 'has_garage', False)
    layout_type = getattr(input_data, 'layout_type', None)
    lot_width = getattr(input_data, 'lot_width_m', None)
    lot_depth = getattr(input_data, 'lot_depth_m', None)
    if hasattr(layout_type, 'value'):
        layout_type = layout_type.value

    templates = get_all_templates(bedrooms)
    if not templates:
        return None

    # Score and rank
    scored = []
    for t in templates:
        score = _score_template(
            t, bedrooms, target_area, has_garage, layout_type,
            lot_width, lot_depth,
        )
        if score > 0:
            scored.append((t, score))

    if not scored:
        return None

    scored.sort(key=lambda x: x[1], reverse=True)
    best, best_score = scored[0]

    if best_score < 30:
        logger.info(f"Repertoire: best score {best_score} too low, falling back")
        return None

    # Adapt to target area and lot dimensions
    if target_area or (lot_width and lot_depth):
        from .adapter import adapt_template
        best = adapt_template(
            best,
            target_area_m2=target_area or ((best.target_area_range[0] + best.target_area_range[1]) / 2),
            lot_width_m=lot_width,
            lot_depth_m=lot_depth,
        )

    logger.info(f"Repertoire: selected {best.id} (score={best_score})")
    return to_legacy_template(best)


def select_top_templates(
    bedrooms: int,
    target_area: float,
    has_garage: bool = False,
    layout_type: str = "open_kitchen",
    lot_width: Optional[float] = None,
    lot_depth: Optional[float] = None,
    max_results: int = 6,
) -> List[Dict[str, Any]]:
    """Retorna top N templates como dicts legados para preview lado a lado.

    Usado pelo frontend para mostrar múltiplas opções ao usuário.
    Cada template é adaptado ao lote informado.
    """
    from .adapter import adapt_template

    templates = get_all_templates(bedrooms)

    scored = []
    for t in templates:
        score = _score_template(
            t, bedrooms, target_area, has_garage, layout_type,
            lot_width, lot_depth,
        )
        if score > 0:
            scored.append((t, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for t, score in scored[:max_results]:
        # Adapt to target area and lot
        adapted = adapt_template(
            t,
            target_area_m2=target_area,
            lot_width_m=lot_width,
            lot_depth_m=lot_depth,
        )
        legacy = to_legacy_template(adapted)
        legacy["_score"] = score
        legacy["_template_name"] = t.name
        legacy["_typology"] = t.typology
        legacy["_tags"] = t.tags
        legacy["_area_range"] = list(t.target_area_range)
        results.append(legacy)

    return results


def _score_template(
    t: TemplateV2,
    bedrooms: Optional[int],
    target_area: Optional[float],
    has_garage: bool,
    layout_type: Optional[str],
    lot_width: Optional[float] = None,
    lot_depth: Optional[float] = None,
) -> float:
    """Score 0-100 para um template."""
    score = 0.0

    # Bedroom match (40 pts)
    if bedrooms is not None:
        if t.bedrooms == bedrooms:
            score += 40
        elif abs(t.bedrooms - bedrooms) == 1:
            score += 15
        else:
            return 0  # incompatible

    # Area fit (30 pts)
    if target_area is not None:
        lo, hi = t.target_area_range
        if lo <= target_area <= hi:
            score += 30
        elif lo * 0.8 <= target_area <= hi * 1.2:
            score += 15
        else:
            score += 5

    # Lot compatibility (15 pts) — prefer templates that fit without crushing
    if lot_width is not None and lot_depth is not None:
        lp = t.lot_placement
        avail_w = lot_width - 2 * lp.setback_side_m
        avail_d = lot_depth - lp.setback_front_m - lp.setback_back_m
        bb = t.bounding_box
        bb_w = bb[2] - bb[0]
        bb_h = bb[3] - bb[1]

        w_ratio = avail_w / bb_w if bb_w > 0 else 1.0
        d_ratio = avail_d / bb_h if bb_h > 0 else 1.0

        if w_ratio >= 0.95 and d_ratio >= 0.95:
            score += 15  # fits well
        elif w_ratio >= 0.80 and d_ratio >= 0.80:
            score += 8   # tight but viable
        elif w_ratio >= 0.65 and d_ratio >= 0.65:
            score += 3   # will need significant compression
        # else: 0 pts — template too large for lot

    # Feature match (10 pts)
    if has_garage and "garagem" in t.tags:
        score += 7
    elif not has_garage and "garagem" not in t.tags:
        score += 3

    if layout_type == "separate_kitchen" and "cozinha_separada" in t.tags:
        score += 3
    elif layout_type == "open_kitchen" and "cozinha_integrada" in t.tags:
        score += 3

    # Variety bonus — L-shapes and varandas get small bonus
    if t.typology in ("l_shape", "u_shape"):
        score += 3
    if "varanda" in t.tags:
        score += 2

    return score
