"""
Extrai alinhamento estrutural do DXF CVS-COB-FOR-006-R00.

Usa POLYLINEs do layer 11 (arestas de vigas) para determinar:
1. Eixos das vigas (centro entre pares paralelos)
2. Painéis de laje (retângulos entre vigas)
3. Posições de pilares (SOLIDs dos layers 21/22)

Gera DXF de alinhamento estrutural.
"""

import ezdxf
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DXF_PATH = "input/CVS-COB-FOR-006-R00.DXF"
OUTPUT_DXF = "output/CVS-COB-alinhamento-estrutural.dxf"
SCALE = 0.5  # DXF → metros reais

# Plan area (DXF units)
X_MIN, X_MAX = 5, 58
Y_MIN, Y_MAX = 28, 58
TOL = 0.015  # tolerance for grouping parallel segments (< half of 2.5cm gap between adjacent beams)


def extract_layer11_segments(msp):
    """Extrai segmentos de arestas de vigas do layer 11."""
    polys = [e for e in msp if e.dxftype() == "POLYLINE" and e.dxf.layer == "11"]
    h_segs = []  # horizontal
    v_segs = []  # vertical

    for p in polys:
        pts = [(v.dxf.location[0], v.dxf.location[1]) for v in p.vertices]
        if len(pts) != 2:
            continue
        x1, y1 = pts[0][0] * SCALE, pts[0][1] * SCALE
        x2, y2 = pts[1][0] * SCALE, pts[1][1] * SCALE

        if abs(y1 - y2) < 0.01:  # horizontal
            h_segs.append({
                "y": (y1 + y2) / 2,
                "x_min": min(x1, x2), "x_max": max(x1, x2),
            })
        elif abs(x1 - x2) < 0.01:  # vertical
            v_segs.append({
                "x": (x1 + x2) / 2,
                "y_min": min(y1, y2), "y_max": max(y1, y2),
            })

    return h_segs, v_segs


def pair_beam_edges(segments, coord_key, span_min_key, span_max_key):
    """Agrupa segmentos paralelos em pares de viga (duas arestas)."""
    # Group by coordinate (same beam = same coord value within tolerance)
    groups = []
    sorted_segs = sorted(segments, key=lambda s: s[coord_key])

    for seg in sorted_segs:
        placed = False
        for g in groups:
            if abs(g["coord"] - seg[coord_key]) < TOL:
                g["segments"].append(seg)
                placed = True
                break
        if not placed:
            groups.append({"coord": seg[coord_key], "segments": [seg]})

    # Now pair groups that are close (beam width apart: 0.14m for 14cm, 0.19m for 19cm)
    beams = []
    used = [False] * len(groups)

    for i in range(len(groups)):
        if used[i]:
            continue
        for j in range(i + 1, len(groups)):
            if used[j]:
                continue
            gap = abs(groups[j]["coord"] - groups[i]["coord"])
            if 0.10 <= gap <= 0.25:  # beam width range: 12cm-22cm
                # Match overlapping segments between the two edge groups
                axis = (groups[i]["coord"] + groups[j]["coord"]) / 2
                width = gap
                edge_lo = min(groups[i]["coord"], groups[j]["coord"])
                edge_hi = max(groups[i]["coord"], groups[j]["coord"])

                # Merge all segment spans
                all_spans = []
                for s in groups[i]["segments"] + groups[j]["segments"]:
                    all_spans.append((s[span_min_key], s[span_max_key]))

                # Merge overlapping spans
                all_spans.sort()
                merged = [all_spans[0]]
                for sp in all_spans[1:]:
                    if sp[0] <= merged[-1][1] + 0.3:  # allow small gap (pillar width)
                        merged[-1] = (merged[-1][0], max(merged[-1][1], sp[1]))
                    else:
                        merged.append(sp)

                beams.append({
                    "axis": round(axis, 4),
                    "width": round(width, 4),
                    "edge_lo": round(edge_lo, 4),
                    "edge_hi": round(edge_hi, 4),
                    "spans": [(round(s[0], 4), round(s[1], 4)) for s in merged],
                })
                used[i] = True
                used[j] = True
                break

    return beams


def extract_pillars(msp):
    """Extrai pilares dos layers 21/22 (SOLIDs agrupados)."""
    solids = [e for e in msp if e.dxftype() == "SOLID" and e.dxf.layer in ("21", "22")]
    plan_solids = []

    for s in solids:
        pts = []
        for attr in ("vtx0", "vtx1", "vtx2", "vtx3"):
            p = getattr(s.dxf, attr, None)
            if p is not None:
                pts.append((p[0] * SCALE, p[1] * SCALE))
        if not pts:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        plan_solids.append({"cx": cx, "cy": cy, "pts": pts})

    # Group close solids
    used = [False] * len(plan_solids)
    pillars = []
    for i, s1 in enumerate(plan_solids):
        if used[i]:
            continue
        group_pts = list(s1["pts"])
        used[i] = True
        for j, s2 in enumerate(plan_solids):
            if used[j]:
                continue
            if abs(s1["cx"] - s2["cx"]) < 0.25 and abs(s1["cy"] - s2["cy"]) < 0.25:
                group_pts.extend(s2["pts"])
                used[j] = True

        xs = [p[0] for p in group_pts]
        ys = [p[1] for p in group_pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        # Filter out non-pillar elements (too large or outside plan)
        if w > 0.40 or h > 0.40:
            continue
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        if cx < 3.0 or cx > 28.0 or cy < 15.0 or cy > 28.0:
            continue
        pillars.append({
            "cx": round((min(xs) + max(xs)) / 2, 4),
            "cy": round((min(ys) + max(ys)) / 2, 4),
            "w_cm": round(w * 100, 0),
            "h_cm": round(h * 100, 0),
            "x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
        })

    return sorted(pillars, key=lambda p: (-p["cy"], p["cx"]))


def extract_text_labels(msp):
    """Extrai labels de pilares, vigas e lajes."""
    labels = {"pillars": [], "beams": [], "slabs": [], "sections": []}
    import re

    for e in msp:
        if e.dxftype() != "TEXT":
            continue
        txt = e.dxf.text.strip()
        x, y = e.dxf.insert[0] * SCALE, e.dxf.insert[1] * SCALE
        layer = e.dxf.layer

        if re.match(r'^P\d', txt):
            labels["pillars"].append({"name": txt, "x": x, "y": y})
        elif re.match(r'^V\d', txt):
            labels["beams"].append({"name": txt, "x": x, "y": y})
        elif re.match(r'^L\d', txt):
            labels["slabs"].append({"name": txt, "x": x, "y": y})
        elif re.match(r'^\d+/\d+$', txt):
            labels["sections"].append({"text": txt, "x": x, "y": y})

    return labels


def find_slab_panel(label_x, label_y, h_beams, v_beams):
    """Encontra o painel de laje que contém o ponto (label_x, label_y).

    Retorna o retângulo definido pelos eixos de vigas mais próximos em cada direção.
    """
    # Find bounding horizontal beams (above and below)
    below = None  # highest H-beam below label
    above = None  # lowest H-beam above label

    for b in h_beams:
        # Check if beam spans cover the label X position
        covers_x = any(s[0] - 0.1 <= label_x <= s[1] + 0.1 for s in b["spans"])
        if not covers_x:
            continue
        if b["axis"] < label_y:
            if below is None or b["axis"] > below["axis"]:
                below = b
        elif b["axis"] > label_y:
            if above is None or b["axis"] < above["axis"]:
                above = b

    # Find bounding vertical beams (left and right)
    left = None
    right = None

    for b in v_beams:
        covers_y = any(s[0] - 0.1 <= label_y <= s[1] + 0.1 for s in b["spans"])
        if not covers_y:
            continue
        if b["axis"] < label_x:
            if left is None or b["axis"] > left["axis"]:
                left = b
        elif b["axis"] > label_x:
            if right is None or b["axis"] < right["axis"]:
                right = b

    if not all([below, above, left, right]):
        return None

    # Slab inner edges = beam inner edges (edge closer to slab center)
    y_bot = below["edge_hi"]  # top edge of bottom beam
    y_top = above["edge_lo"]  # bottom edge of top beam
    x_left = left["edge_hi"]  # right edge of left beam
    x_right = right["edge_lo"]  # left edge of right beam

    return {
        "x_min": round(x_left, 4),
        "x_max": round(x_right, 4),
        "y_min": round(y_bot, 4),
        "y_max": round(y_top, 4),
        "beam_south": below["axis"],
        "beam_north": above["axis"],
        "beam_west": left["axis"],
        "beam_east": right["axis"],
    }


def extract_slab_thickness(label_name, all_texts):
    """Encontra espessura da laje a partir dos textos próximos ao label."""
    import re
    # Look for "h=XX" text near the slab label
    for t in all_texts:
        if t.dxftype() != "TEXT":
            continue
        txt = t.dxf.text.strip()
        m = re.match(r'h\s*=\s*(\d+)', txt)
        if m:
            x, y = t.dxf.insert[0] * SCALE, t.dxf.insert[1] * SCALE
            # Check labels collection to find matching slab
            # This is called per-slab so we just return matches
            yield {"thickness_cm": int(m.group(1)), "x": x, "y": y, "text": txt}


def generate_alignment_dxf(h_beams, v_beams, pillars, slab_panels, labels, output_path):
    """Gera DXF de alinhamento estrutural."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Create layers
    doc.layers.add("PILARES", color=1)  # red
    doc.layers.add("VIGAS_H", color=5)  # blue
    doc.layers.add("VIGAS_V", color=5)  # blue
    doc.linetypes.add("DASHED", pattern=[0.5, 0.25, -0.25])
    doc.layers.add("EIXOS_VIGAS", color=3, linetype="DASHED")  # green
    doc.layers.add("LAJES", color=4)  # cyan
    doc.layers.add("LABELS", color=7)  # white
    doc.layers.add("DIMS", color=8)  # gray

    # Draw pillar rectangles
    for p in pillars:
        msp.add_lwpolyline(
            [(p["x_min"], p["y_min"]), (p["x_max"], p["y_min"]),
             (p["x_max"], p["y_max"]), (p["x_min"], p["y_max"])],
            close=True,
            dxfattribs={"layer": "PILARES"},
        )
        # Pillar label
        for lbl in labels["pillars"]:
            if abs(lbl["x"] - p["cx"]) < 0.5 and abs(lbl["y"] - p["cy"]) < 0.5:
                msp.add_text(
                    lbl["name"],
                    height=0.12,
                    dxfattribs={"layer": "LABELS", "insert": (p["cx"], p["cy"] + 0.15)},
                )
                break

    # Draw horizontal beams (filled outline)
    for b in h_beams:
        for span in b["spans"]:
            # Beam outline
            msp.add_lwpolyline(
                [(span[0], b["edge_lo"]), (span[1], b["edge_lo"]),
                 (span[1], b["edge_hi"]), (span[0], b["edge_hi"])],
                close=True,
                dxfattribs={"layer": "VIGAS_H"},
            )
            # Axis line (dashed)
            msp.add_line(
                (span[0], b["axis"]), (span[1], b["axis"]),
                dxfattribs={"layer": "EIXOS_VIGAS"},
            )

    # Draw vertical beams
    for b in v_beams:
        for span in b["spans"]:
            msp.add_lwpolyline(
                [(b["edge_lo"], span[0]), (b["edge_hi"], span[0]),
                 (b["edge_hi"], span[1]), (b["edge_lo"], span[1])],
                close=True,
                dxfattribs={"layer": "VIGAS_V"},
            )
            msp.add_line(
                (b["axis"], span[0]), (b["axis"], span[1]),
                dxfattribs={"layer": "EIXOS_VIGAS"},
            )

    # Draw slab panels (supports arbitrary polygons: rectangles, L-shapes, etc.)
    from shapely.geometry import Polygon as ShapelyPolygon
    for name, panel in slab_panels.items():
        if panel is None:
            continue
        vertices = panel["vertices"]
        # Draw polygon contour
        msp.add_lwpolyline(
            [(x, y) for x, y in vertices],
            close=True,
            dxfattribs={"layer": "LAJES"},
        )
        # Calculate centroid and area
        poly = ShapelyPolygon(vertices)
        cx, cy = poly.centroid.x, poly.centroid.y
        area = poly.area
        msp.add_text(
            f"{name}",
            height=0.15,
            dxfattribs={"layer": "LABELS", "insert": (cx - 0.2, cy + 0.1)},
        )
        msp.add_text(
            f"A={area:.1f}m²",
            height=0.10,
            dxfattribs={"layer": "DIMS", "insert": (cx - 0.3, cy - 0.15)},
        )

    doc.saveas(output_path)
    print(f"  DXF salvo: {output_path}")


def main():
    doc = ezdxf.readfile(DXF_PATH)
    msp = doc.modelspace()

    print("=" * 70)
    print("EXTRAÇÃO DE ALINHAMENTO ESTRUTURAL")
    print("CVS-COB-FOR-006-R00 — Cobertura +1330,40m")
    print("=" * 70)

    # 1. Extract beam edges from layer 11
    h_segs, v_segs = extract_layer11_segments(msp)
    print(f"\nSegmentos layer 11: {len(h_segs)} horizontais, {len(v_segs)} verticais")

    # 2. Pair into beams
    h_beams = pair_beam_edges(h_segs, "y", "x_min", "x_max")
    v_beams = pair_beam_edges(v_segs, "x", "y_min", "y_max")

    print(f"\n{'='*70}")
    print("VIGAS HORIZONTAIS")
    print(f"{'='*70}")
    h_beams.sort(key=lambda b: b["axis"])
    for b in h_beams:
        spans_str = " + ".join(f"[{s[0]:.2f}→{s[1]:.2f}]" for s in b["spans"])
        print(f"  Y={b['axis']:.3f}m  w={b['width']*100:.0f}cm  "
              f"edges=[{b['edge_lo']:.3f},{b['edge_hi']:.3f}]  {spans_str}")

    print(f"\n{'='*70}")
    print("VIGAS VERTICAIS")
    print(f"{'='*70}")
    v_beams.sort(key=lambda b: b["axis"])
    for b in v_beams:
        spans_str = " + ".join(f"[{s[0]:.2f}→{s[1]:.2f}]" for s in b["spans"])
        print(f"  X={b['axis']:.3f}m  w={b['width']*100:.0f}cm  "
              f"edges=[{b['edge_lo']:.3f},{b['edge_hi']:.3f}]  {spans_str}")

    # 3. Extract pillars
    pillars = extract_pillars(msp)
    print(f"\n{'='*70}")
    print(f"PILARES ({len(pillars)})")
    print(f"{'='*70}")
    for p in pillars:
        print(f"  ({p['cx']:.3f}, {p['cy']:.3f})  {p['w_cm']:.0f}x{p['h_cm']:.0f}cm")

    # 4. Extract labels
    labels = extract_text_labels(msp)
    print(f"\nLabels: {len(labels['pillars'])} pilares, {len(labels['beams'])} vigas, "
          f"{len(labels['slabs'])} lajes, {len(labels['sections'])} seções")

    # 5. Slab thickness from DXF texts
    all_texts = list(msp.query("TEXT"))
    thickness_map = {}
    import re
    for t in all_texts:
        txt = t.dxf.text.strip()
        m = re.match(r'h\s*=\s*(\d+)', txt)
        if m:
            x, y = t.dxf.insert[0] * SCALE, t.dxf.insert[1] * SCALE
            thickness_map[(x, y)] = int(m.group(1))

    # Associate thickness with nearest slab label
    slab_thickness = {}
    for slbl in labels["slabs"]:
        best_dist = 999
        best_h = None
        for (tx, ty), h_cm in thickness_map.items():
            d = ((slbl["x"] - tx) ** 2 + (slbl["y"] - ty) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_h = h_cm
        slab_thickness[slbl["name"]] = best_h

    print(f"\n{'='*70}")
    print("ESPESSURAS DAS LAJES")
    print(f"{'='*70}")
    for name, h in sorted(slab_thickness.items()):
        print(f"  {name}: h={h}cm")

    # 6. Slab panels — definidos manualmente com base nas arestas de vigas
    # Corrigidos para evitar sobreposição (L5/L6/L7)
    print(f"\n{'='*70}")
    print("PAINÉIS DE LAJE (retângulos entre vigas — sem sobreposição)")
    print(f"{'='*70}")

    # Painéis definidos pelos contornos reais (arestas internas das vigas).
    # Lajes L5, L6 e L7 são em forma de L — vigas V16a, V17a e V18a
    # criam os degraus nos contornos.
    # Formato: lista de vértices (x, y) — polígonos arbitrários.
    MANUAL_PANELS = {
        "L1":  [(4.142, 17.556), (10.027, 17.556), (10.027, 21.716), (4.142, 21.716)],
        "L2":  [(10.167, 18.396), (15.022, 18.396), (15.022, 21.716), (10.167, 21.716)],
        "L3":  [(15.162, 18.396), (18.477, 18.396), (18.477, 21.716), (15.162, 21.716)],
        "L4":  [(14.052, 21.856), (18.477, 21.856), (18.477, 23.041), (14.052, 23.041)],
        # L5: forma de L — base completa + extensão superior direita (gap no H-beam Y=23.116)
        "L5":  [(18.616, 22.021), (21.632, 22.021), (21.632, 24.221),
                (20.252, 24.221), (20.252, 23.041), (18.616, 23.041)],
        # L6: forma de L — corpo principal + extensão superior direita (V16a termina)
        "L6":  [(16.582, 23.191), (20.112, 23.191), (20.112, 24.361),
                (20.872, 24.361), (20.872, 26.281), (16.582, 26.281)],
        # L7: forma de L — base estreita (V18a limita) + parte superior ampla (V17a limita)
        "L7":  [(21.772, 23.191), (25.827, 23.191), (25.827, 26.281),
                (21.012, 26.281), (21.012, 24.361), (21.772, 24.361)],
        "L8":  [(16.442, 26.421), (26.797, 26.421), (26.797, 27.251), (16.442, 27.251)],
        "L9":  [(21.772, 18.396), (25.827, 18.396), (25.827, 23.041), (21.772, 23.041)],
        "L10": [(18.616, 18.396), (21.632, 18.396), (21.632, 21.881), (18.616, 21.881)],
    }

    slab_panels = {}
    from shapely.geometry import Polygon as ShapelyPolygon
    for name in sorted(MANUAL_PANELS.keys()):
        vertices = MANUAL_PANELS[name]
        poly = ShapelyPolygon(vertices)
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        slab_panels[name] = {"vertices": vertices}
        h_cm = slab_thickness.get(name, "?")
        n_vert = len(vertices)
        shape = "L" if n_vert == 6 else "rect"
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        print(f"  {name:<4}: ({min(xs):.3f},{min(ys):.3f}) → ({max(xs):.3f},{max(ys):.3f})  "
              f"{bb_w:.2f}×{bb_h:.2f}m  A={poly.area:.1f}m²  h={h_cm}cm  [{shape}]")

    # 7. Generate alignment DXF
    print(f"\n{'='*70}")
    print("GERANDO DXF DE ALINHAMENTO")
    print(f"{'='*70}")
    Path("output").mkdir(exist_ok=True)
    generate_alignment_dxf(h_beams, v_beams, pillars, slab_panels, labels, OUTPUT_DXF)

    # 8. Print data for run_cvs_cob.py
    print(f"\n{'='*70}")
    print("DADOS PARA run_cvs_cob.py")
    print(f"{'='*70}")
    print("\nSLABS = [")
    for slbl in sorted(labels["slabs"], key=lambda s: s["name"]):
        name = slbl["name"]
        panel = slab_panels.get(name)
        h_cm = slab_thickness.get(name, 12)
        if panel:
            verts = panel["vertices"]
            verts_str = ", ".join(f"({v[0]:.4f}, {v[1]:.4f})" for v in verts)
            print(f'    {{"name": "{name}", "thickness_cm": {h_cm},')
            print(f'     "vertices": [{verts_str}]}},')
        else:
            print(f'    # {name}: panel not found — check manually')
    print("]")

    print("\nPILLARS = [")
    for i, p in enumerate(pillars):
        # Find matching label
        best_name = f"P?{i}"
        best_dist = 999
        for plbl in labels["pillars"]:
            d = ((plbl["x"] - p["cx"]) ** 2 + (plbl["y"] - p["cy"]) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_name = plbl["name"]
        print(f'    {{"name": "{best_name}", "x": {p["cx"]:.4f}, "y": {p["cy"]:.4f}, '
              f'"w_cm": {p["w_cm"]:.0f}, "d_cm": {p["h_cm"]:.0f}}},')
    print("]")


if __name__ == "__main__":
    main()
