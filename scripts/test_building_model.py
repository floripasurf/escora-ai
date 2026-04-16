"""Test BuildingModel — generates all views from a single unified model."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.drawing import TechnicalSheet, BuildingModel
from src.drawing.sheet import TitleBlockInfo

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "drawing_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_house() -> BuildingModel:
    """Create a 2-bedroom house model with real materials."""
    model = BuildingModel(
        ceiling_height=2.80,
        default_wall_material="bloco_ceramico_14",
        default_slab_material="pre_moldada_12",
    )

    # External walls (7m x 10m)
    w0 = model.add_wall((0, 0), (7, 0))    # South
    w1 = model.add_wall((7, 0), (7, 10))   # East
    w2 = model.add_wall((7, 10), (0, 10))  # North
    w3 = model.add_wall((0, 10), (0, 0))   # West

    # Internal walls — vedacao (drywall)
    model.add_wall((0, 5), (4, 5), material="drywall_simples")
    model.add_wall((4, 0), (4, 5), material="drywall_simples")
    model.add_wall((4, 5), (4, 10), material="drywall_simples")
    model.add_wall((0, 7.5), (4, 7.5), material="drywall_simples")

    # Openings — doors
    model.add_opening("door", wall_id=w0, position=1.0, width=0.80, height=2.10)
    model.add_opening("door", wall_id=4, position=1.5, width=0.70, height=2.10)
    model.add_opening("door", wall_id=7, position=1.0, width=0.70, height=2.10)

    # Openings — windows
    model.add_opening("window", wall_id=w0, position=3.0, width=1.50, height=1.20, sill_height=1.00)
    model.add_opening("window", wall_id=w0, position=5.5, width=1.00, height=0.80, sill_height=1.40)
    model.add_opening("window", wall_id=w3, position=6.0, width=1.00, height=1.20, sill_height=1.00)
    model.add_opening("window", wall_id=w3, position=8.5, width=1.00, height=1.20, sill_height=1.00)

    # Slabs
    model.add_slab()                               # Floor
    model.add_slab(is_ceiling=True)                # Ceiling

    # Roof
    model.set_roof(style="gable", material="ceramica_colonial", slope_pct=30, overhang_m=0.60)

    # Foundation
    model.set_foundation(material="sapata_corrida")

    # Room labels
    model.add_room("Sala/Cozinha", (2.0, 2.5), 20.0, finish="porcelanato")
    model.add_room("Banheiro", (5.5, 2.5), 4.5, finish="ceramica")
    model.add_room("Quarto 1", (2.0, 6.25), 10.0, finish="porcelanato")
    model.add_room("Quarto 2", (2.0, 8.75), 10.0, finish="porcelanato")
    model.add_room("Serviço", (5.5, 7.5), 7.5, finish="ceramica")

    return model


def test_model_info(model: BuildingModel):
    """Print model summary."""
    print(f"  Model: {model}")
    print(f"  Bounding box: {model.bounding_box}")
    print(f"  Built area: {model.built_area_m2:.1f} m²")
    print(f"  Total height: {model.total_height_m:.2f} m")
    print(f"  Wall area: {model.total_wall_area_m2:.1f} m²")
    print(f"  Total weight: {model.total_weight_kn:.1f} kN")
    print()

    print("  Bill of Materials:")
    for item in model.bill_of_materials():
        mat = item.get("material", "?")
        qty = item.get("quantity", 0)
        unit = item.get("unit", "")
        cat = item.get("category", "")
        print(f"    {cat}: {mat} — {qty} {unit}")
    print()


def test_plan(model: BuildingModel):
    """Generate floor plan from model."""
    print("  Generating floor plan...")
    sheet = TechnicalSheet("A2", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="PLANTA BAIXA - PAV. TERREO",
        drawing_number="01/04",
        author="Escora.AI",
        responsible="Eng. Demo",
        date="2026-04-15",
        scale_str="1:50",
        sheet_format="A2",
    ))
    sheet.draw_plan(model, auto_dim=True)

    # Cutting plane
    sheet.add_cutting_plane((-0.5, 5), (7.5, 5), label="A")

    path = sheet.save(str(OUTPUT_DIR / "model_01_planta.dxf"))
    print(f"    Saved: {path}")


def test_section(model: BuildingModel):
    """Generate section from model."""
    print("  Generating section...")
    sheet = TechnicalSheet("A2", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="CORTE A-A",
        drawing_number="02/04",
        author="Escora.AI",
        date="2026-04-15",
        scale_str="1:50",
        sheet_format="A2",
    ))
    sheet.draw_section_from_model(
        model,
        cut_start=(0, 5), cut_end=(7, 5),
        label="A-A", direction="north",
        origin=(0.05, 0.05),
    )
    path = sheet.save(str(OUTPUT_DIR / "model_02_corte.dxf"))
    print(f"    Saved: {path}")


def test_elevation(model: BuildingModel):
    """Generate elevation from model."""
    print("  Generating elevation...")
    sheet = TechnicalSheet("A2", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="FACHADA FRONTAL (SUL)",
        drawing_number="03/04",
        author="Escora.AI",
        date="2026-04-15",
        scale_str="1:50",
        sheet_format="A2",
    ))
    sheet.draw_elevation_from_model(model, direction="south", origin=(0.05, 0.05))

    # Add height dimension
    sheet.add_dimension((0.05, 0.05), (0.05, 2.85), offset=-0.8, angle=90)

    path = sheet.save(str(OUTPUT_DIR / "model_03_fachada.dxf"))
    print(f"    Saved: {path}")


def test_isometric(model: BuildingModel):
    """Generate isometric from model."""
    print("  Generating isometric...")
    sheet = TechnicalSheet("A3", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="PERSPECTIVA ISOMETRICA",
        drawing_number="04/04",
        author="Escora.AI",
        date="2026-04-15",
        scale_str="1:50",
        sheet_format="A3",
    ))
    sheet.draw_isometric_from_model(model, draw_hidden=True)
    path = sheet.save(str(OUTPUT_DIR / "model_04_isometrica.dxf"))
    print(f"    Saved: {path}")


def test_paper_space(model: BuildingModel):
    """Generate multi-scale paper space layout."""
    print("  Generating paper space layout...")
    sheet = TechnicalSheet("A1", scale="1:50")

    # Draw all views in model space at different positions
    sheet.draw_plan(model, auto_dim=True)

    # Section offset to the right
    sheet.draw_section_from_model(
        model,
        cut_start=(0, 5), cut_end=(7, 5),
        label="A-A", direction="north",
        origin=(12, 0),
    )

    # Create paper space with viewports
    from src.drawing.paper_space import PaperSpaceLayout
    ps = PaperSpaceLayout(sheet, "A1")
    ps.draw_paper_border()
    ps.draw_paper_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="PRANCHA UNICA",
        drawing_number="01/01",
        author="Escora.AI",
        responsible="Eng. Demo",
        date="2026-04-15",
        scale_str="INDICADAS",
        sheet_format="A1",
    ))

    # Viewport 1: Plan at 1:50
    bb = model.bounding_box
    plan_cx = (bb[0] + bb[2]) / 2
    plan_cy = (bb[1] + bb[3]) / 2
    ps.add_viewport("PLANTA BAIXA", x_mm=30, y_mm=120, width_mm=400, height_mm=400,
                     scale_factor=50, center_model=(plan_cx, plan_cy))

    # Viewport 2: Section at 1:50
    ps.add_viewport("CORTE A-A", x_mm=460, y_mm=120, width_mm=300, height_mm=200,
                     scale_factor=50, center_model=(15.5, 1.5))

    ps.finalize()
    path = sheet.save(str(OUTPUT_DIR / "model_05_prancha.dxf"))
    print(f"    Saved: {path}")


def main():
    print("=" * 60)
    print("BuildingModel Test — Unified Model → All Views")
    print("=" * 60)
    print()

    model = build_house()
    test_model_info(model)
    test_plan(model)
    test_section(model)
    test_elevation(model)
    test_isometric(model)
    test_paper_space(model)

    print()
    print(f"All drawings saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
