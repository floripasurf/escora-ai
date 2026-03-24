"""Modelo Pydantic para o projeto de escoramento."""

from pydantic import BaseModel, Field
from typing import List
from .slab import Slab
from .shore import PositionedShore, ShoreCatalogEntry


class ShoringResult(BaseModel):
    """Resultado do cálculo de escoramento para uma laje."""
    slab: Slab
    total_load_kn: float = Field(description="Carga total majorada (kN)")
    self_weight_kn: float = Field(description="Peso próprio da laje (kN)")
    live_load_kn: float = Field(description="Sobrecarga (kN)")
    selected_shore: ShoreCatalogEntry = Field(description="Modelo de escora selecionado")
    shores: List[PositionedShore] = Field(description="Escoras posicionadas")
    grid_nx: int = Field(description="Quantidade de escoras na direção X")
    grid_ny: int = Field(description="Quantidade de escoras na direção Y")
    spacing_x_m: float = Field(description="Espaçamento efetivo X (m)")
    spacing_y_m: float = Field(description="Espaçamento efetivo Y (m)")
    load_per_shore_kn: float = Field(description="Carga por escora (kN)")


class Project(BaseModel):
    """Projeto completo de escoramento."""
    input_file: str
    output_file: str = ""
    results: List[ShoringResult] = Field(default_factory=list)

    @property
    def total_shores(self) -> int:
        return sum(len(r.shores) for r in self.results)
