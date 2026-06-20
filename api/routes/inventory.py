"""Inventory endpoints scoped to the selected branch."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.deps import get_current_branch, require_owner_or_admin
from api.services.inventory_service import (
    InventoryItemInput,
    delete_inventory_item,
    import_inventory_csv,
    import_inventory_xlsx,
    inventory_history,
    inventory_summary,
    preview_inventory_csv,
    preview_inventory_xlsx,
    replace_inventory,
    restore_inventory_history,
    template_csv,
    template_xlsx,
    upsert_inventory_item,
)
from src.auth.branches import Branch, User

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


class InventoryItemRequest(BaseModel):
    section: Literal["telescopic_shores", "tower_modules", "distribution_beams", "accessories"]
    qty: int = Field(ge=0)
    capacity_kn: Optional[float] = Field(default=None, ge=0)
    height_min_m: Optional[float] = Field(default=None, ge=0)
    height_max_m: Optional[float] = Field(default=None, ge=0)
    capacity_curve: Optional[list[list[float]]] = None
    notes: str = ""

    def to_input(self) -> InventoryItemInput:
        if self.height_min_m is not None and self.height_max_m is not None:
            if self.height_min_m > self.height_max_m:
                raise ValueError("Altura minima nao pode ser maior que a maxima")
        if self.capacity_curve is not None:
            for pair in self.capacity_curve:
                if len(pair) != 2:
                    raise ValueError("Curva de capacidade deve usar pares [altura, capacidade]")
        return InventoryItemInput(
            section=self.section,
            qty=self.qty,
            capacity_kn=self.capacity_kn,
            height_min_m=self.height_min_m,
            height_max_m=self.height_max_m,
            capacity_curve=self.capacity_curve,
            notes=self.notes,
        )


class InventoryReplaceRequest(BaseModel):
    locadora: Optional[str] = None
    telescopic_shores: dict = Field(default_factory=dict)
    tower_modules: dict = Field(default_factory=dict)
    distribution_beams: dict = Field(default_factory=dict)
    accessories: dict = Field(default_factory=dict)


@router.get("")
async def get_inventory(branch: Branch = Depends(get_current_branch)):
    return inventory_summary(branch)


@router.put("")
async def put_inventory(
    body: InventoryReplaceRequest,
    branch: Branch = Depends(get_current_branch),
    user: User = Depends(require_owner_or_admin),
):
    try:
        return replace_inventory(branch, body.model_dump(), actor=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/items/{model_id}")
async def put_inventory_item(
    model_id: str,
    body: InventoryItemRequest,
    branch: Branch = Depends(get_current_branch),
    user: User = Depends(require_owner_or_admin),
):
    try:
        return upsert_inventory_item(branch, model_id, body.to_input(), actor=user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/items/{model_id}")
async def delete_item(
    model_id: str,
    branch: Branch = Depends(get_current_branch),
    user: User = Depends(require_owner_or_admin),
):
    try:
        return delete_inventory_item(branch, model_id, actor=user.username)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Item nao encontrado") from e


def _decode_upload(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _is_xlsx(filename: str, raw: bytes) -> bool:
    return filename.lower().endswith(".xlsx") or raw[:2] == b"PK"


@router.post("/import-preview")
async def import_preview(
    file: UploadFile = File(...),
    branch: Branch = Depends(get_current_branch),
    _: User = Depends(require_owner_or_admin),
):
    raw = await file.read()
    filename = file.filename or ""
    try:
        if _is_xlsx(filename, raw):
            return preview_inventory_xlsx(branch, raw, filename=filename)
        return preview_inventory_csv(branch, _decode_upload(raw), filename=filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/import-csv")
async def import_csv(
    mode: Literal["replace", "update_quantities"] = "replace",
    file: UploadFile = File(...),
    branch: Branch = Depends(get_current_branch),
    user: User = Depends(require_owner_or_admin),
):
    raw = await file.read()
    filename = file.filename or ""
    try:
        if _is_xlsx(filename, raw):
            return import_inventory_xlsx(
                branch,
                raw,
                actor=user.username,
                filename=filename,
                mode=mode,
            )
        return import_inventory_csv(
            branch,
            _decode_upload(raw),
            actor=user.username,
            filename=filename,
            mode=mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/history")
async def get_history(
    limit: int = 20,
    branch: Branch = Depends(get_current_branch),
    _: User = Depends(require_owner_or_admin),
):
    return inventory_history(branch, limit=limit)


@router.post("/history/{entry_id}/restore")
async def restore_history_entry(
    entry_id: str,
    branch: Branch = Depends(get_current_branch),
    user: User = Depends(require_owner_or_admin),
):
    try:
        return restore_inventory_history(branch, entry_id, actor=user.username)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Historico nao encontrado") from e


@router.get("/template.csv")
async def download_template():
    return Response(
        content=template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modelo-inventario.csv"'},
    )


@router.get("/template.xlsx")
async def download_template_xlsx():
    return Response(
        content=template_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="modelo-inventario.xlsx"'},
    )
