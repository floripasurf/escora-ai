"""Convenções de rotulagem e classificação de painéis de escoramento.

Centraliza constantes usadas pelo pipeline de cálculo, writer DXF, gerador
Excel e CLI para que todos emitam rótulos consistentes por categoria.

Categorias suportadas:
    laje, beiral, balanco, platibanda, marquise, cantilever

As regex `STRUCTURAL_LABEL_PATTERNS` e `ROOM_LABEL_PATTERNS` procuram texto
próximo ao polígono para extrair:
    - nome estrutural (ex.: "L3", "LAJE 7") → vira rótulo principal
    - nome do cômodo (ex.: "QUARTO 1", "COZINHA") → vira `room_hint`
"""

import re
from typing import Dict, Tuple


# Categoria default e lista oficial
CATEGORY_DEFAULT = "laje"
CATEGORIES: Tuple[str, ...] = (
    "laje", "beiral", "balanco", "platibanda", "marquise", "cantilever",
)


# Palavras-chave em nomes de layer que mapeiam para cada categoria.
# Ordem importa: a primeira categoria com match vence, então colocamos
# platibanda antes de beiral para pegar "PLATIBANDA_BEIRAL" corretamente.
CATEGORY_LAYER_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "platibanda": ("PLATIBANDA", "MURETA", "PARAPEITO", "PARAPET"),
    "marquise":   ("MARQUISE", "CANOPY"),
    "beiral":     ("BEIRAL", "EAVE"),
    "balanco":    ("BALANCO", "BALANÇO"),
    "cantilever": ("CANTILEVER",),
}


# Rótulo em Português Brasileiro exibido no DXF/Excel.
CATEGORY_LABELS_PT: Dict[str, str] = {
    "laje":       "Laje",
    "beiral":     "Beiral",
    "balanco":    "Balanço",
    "platibanda": "Platibanda",
    "marquise":   "Marquise",
    "cantilever": "Cantilever",
}


# Cor AutoCAD (índice ACI) para cada categoria no layer VOLUMES.
# 1=vermelho, 2=amarelo, 3=verde, 4=ciano, 5=azul, 6=magenta, 7=branco/preto.
CATEGORY_DXF_COLOR: Dict[str, int] = {
    "laje":       7,   # branco/preto — painel principal
    "beiral":     4,   # ciano
    "balanco":    6,   # magenta
    "platibanda": 2,   # amarelo — visual imediato de "perímetro"
    "marquise":   4,   # ciano (similar a beiral)
    "cantilever": 6,   # magenta (similar a balanço)
}


# Padrões que identificam uma laje estrutural (L3, LAJE 7, LJ-12).
# Casa tanto "L3" quanto "LAJE 7" ou "LJ-12". Usar IGNORECASE.
STRUCTURAL_LABEL_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"\b(L\d{1,3}[A-Z]?)\b", re.IGNORECASE),
    re.compile(r"\bLAJE\s*([A-Z]?\d{1,3}[A-Z]?)\b", re.IGNORECASE),
    re.compile(r"\bLJ[-\s]?(\d{1,3}[A-Z]?)\b", re.IGNORECASE),
)


# Padrões que identificam um cômodo (QUARTO 1, COZINHA, BANHEIRO…).
# A ideia é extrair o nome amigável ("Quarto 1") para colar em parênteses.
ROOM_LABEL_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(
        r"\b(QUARTO|DORM(?:IT[ÓO]RIO)?|SU[ÍI]TE|SALA|COZINHA|BANHEIRO|BWC|"
        r"LAVABO|VARANDA|SACADA|ÁREA\s+SERV(?:I[ÇC]O)?|AREA\s+SERV(?:I[ÇC]O)?|"
        r"HALL|CIRCULA[CÇ][ÃA]O|GARAGEM|LAVANDERIA|ESCRIT[ÓO]RIO|"
        r"TERRA[ÇC]O|[AÁ]TICO|COBERTURA|COPA|DESPENSA|CLOSET|ROUPARIA)"
        r"(?:\s+(\d{1,2}))?"
        r"\b",
        re.IGNORECASE,
    ),
)


def classify_layer(layer_name: str) -> str | None:
    """Retorna a categoria para um nome de layer ou None se não houver match.

    Usado pelo estágio de cálculo para fazer bypass do filtro de faixa fina
    quando o painel pertence a layer explicitamente categorizada.
    """
    if not layer_name:
        return None
    upper = layer_name.upper()
    for category, keywords in CATEGORY_LAYER_KEYWORDS.items():
        if any(kw in upper for kw in keywords):
            return category
    return None


def _titleize_room(raw: str) -> str:
    """Formata texto bruto de cômodo em título PT-BR (QUARTO 1 -> Quarto 1)."""
    cleaned = " ".join(raw.split())
    return cleaned.title()


def extract_room_hint(text: str) -> str | None:
    """Procura padrão de cômodo no texto. Retorna nome formatado ou None."""
    if not text:
        return None
    for pattern in ROOM_LABEL_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1)
            number = m.group(2) if m.lastindex and m.lastindex >= 2 else None
            label = name if not number else f"{name} {number}"
            return _titleize_room(label)
    return None


def extract_structural_name(text: str) -> str | None:
    """Procura padrão tipo 'L3' ou 'LAJE 7'. Retorna nome canonizado ou None."""
    if not text:
        return None
    for pattern in STRUCTURAL_LABEL_PATTERNS:
        m = pattern.search(text)
        if m:
            num = m.group(1)
            # Canonicaliza para "L<N>" (ex.: "LJ-12" → "L12")
            num_clean = num.upper().replace("-", "").replace(" ", "")
            if num_clean.startswith("L"):
                return num_clean
            return f"L{num_clean}"
    return None
