"""Leitura de arquivos DXF via ezdxf."""

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import DXFEntity
from typing import List, Dict, Optional


def read_dxf(filepath: str) -> Drawing:
    """Abre um arquivo DXF e retorna o documento ezdxf."""
    return ezdxf.readfile(filepath)


def list_layers(doc: Drawing) -> List[str]:
    """Lista todos os layers do documento."""
    return [layer.dxf.name for layer in doc.layers]


def get_entities_by_layer(doc: Drawing, layer_name: str) -> List[DXFEntity]:
    """Retorna todas as entidades de um layer específico."""
    msp = doc.modelspace()
    return [e for e in msp if e.dxf.layer == layer_name]


def get_polylines_by_layer(doc: Drawing, layer_name: str) -> List[DXFEntity]:
    """Retorna LWPOLYLINE e POLYLINE de um layer."""
    entities = get_entities_by_layer(doc, layer_name)
    return [
        e for e in entities
        if e.dxftype() in ("LWPOLYLINE", "POLYLINE")
    ]


def find_slab_layers(doc: Drawing) -> List[str]:
    """Identifica layers que contêm lajes (padrão: LAJE_XXcm ou SLAB_XX)."""
    slab_layers = []
    for layer_name in list_layers(doc):
        upper = layer_name.upper()
        if "LAJE" in upper or "SLAB" in upper:
            slab_layers.append(layer_name)
    return slab_layers


def get_document_info(doc: Drawing) -> Dict[str, any]:
    """Retorna informações gerais do documento DXF."""
    msp = doc.modelspace()
    entity_counts: Dict[str, int] = {}
    for entity in msp:
        etype = entity.dxftype()
        entity_counts[etype] = entity_counts.get(etype, 0) + 1

    return {
        "version": doc.dxfversion,
        "layers": list_layers(doc),
        "layer_count": len(list_layers(doc)),
        "entity_counts": entity_counts,
        "total_entities": sum(entity_counts.values()),
    }
