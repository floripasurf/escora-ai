"""
Deep structural analysis of DXF formwork drawing.
Extracts pillars (SOLID), beams (V-labels + LINE pairs), slabs (L-labels),
and line geometry from the plan area.

Scale 1:50 => real_meters = DXF_value * 0.5
"""

import ezdxf
import re
from collections import defaultdict

DXF_PATH = "./input/CVS-COB-FOR-006-R00.DXF"
SCALE = 0.5  # DXF units -> real meters

# Plan area bounds (DXF units)
X_MIN, X_MAX = 5, 58
Y_MIN, Y_MAX = 28, 58

TOL = 0.02  # tolerance for grouping parallel lines (DXF units)
BEAM_WIDTH_TOL = 0.05  # tolerance for matching beam-width pairs


def in_plan(x, y):
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX


def to_real(v):
    return round(v * SCALE, 3)


def main():
    doc = ezdxf.readfile(DXF_PATH)
    msp = doc.modelspace()

    # ── 1. Layer inventory ──────────────────────────────────────────────
    layer_entities = defaultdict(lambda: defaultdict(int))
    all_entities = list(msp)
    for e in all_entities:
        layer_entities[e.dxf.layer][e.dxftype()] += 1

    print("=" * 80)
    print("1. LAYER INVENTORY")
    print("=" * 80)
    for layer in sorted(layer_entities.keys()):
        types = layer_entities[layer]
        total = sum(types.values())
        detail = ", ".join(f"{t}: {c}" for t, c in sorted(types.items()))
        print(f"  [{layer}] total={total}  |  {detail}")

    # ── 2. SOLID entities (pillars) ─────────────────────────────────────
    print("\n" + "=" * 80)
    print("2. SOLID ENTITIES (PILLARS) in plan area")
    print("=" * 80)
    solids = [e for e in all_entities if e.dxftype() == "SOLID"]
    print(f"  Total SOLIDs in file: {len(solids)}")

    plan_solids = []
    for s in solids:
        # SOLID has 4 vertices: vtx0, vtx1, vtx2, vtx3
        pts = []
        for attr in ("vtx0", "vtx1", "vtx2", "vtx3"):
            p = getattr(s.dxf, attr, None)
            if p is not None:
                pts.append((p[0], p[1]))
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        if in_plan(cx, cy):
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            plan_solids.append({
                "layer": s.dxf.layer,
                "cx": cx, "cy": cy,
                "w": w, "h": h,
                "pts": pts,
            })

    plan_solids.sort(key=lambda s: (s["cy"], s["cx"]))
    print(f"  SOLIDs in plan area: {len(plan_solids)}")
    print()
    # Group solids that are very close together (same pillar, multiple triangles)
    # SOLID in DXF can be two triangles forming a rectangle
    pillar_groups = []
    used = [False] * len(plan_solids)
    for i, s1 in enumerate(plan_solids):
        if used[i]:
            continue
        group = [s1]
        used[i] = True
        for j, s2 in enumerate(plan_solids):
            if used[j]:
                continue
            if abs(s1["cx"] - s2["cx"]) < 0.5 and abs(s1["cy"] - s2["cy"]) < 0.5:
                group.append(s2)
                used[j] = True
        # Compute bounding box of group
        all_pts = []
        for g in group:
            all_pts.extend(g["pts"])
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        pillar_groups.append({
            "layer": group[0]["layer"],
            "n_solids": len(group),
            "x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "cx": (min(xs) + max(xs)) / 2,
            "cy": (min(ys) + max(ys)) / 2,
            "w": max(xs) - min(xs),
            "h": max(ys) - min(ys),
        })

    print(f"  Pillar groups (merged close SOLIDs): {len(pillar_groups)}")
    print(f"  {'#':<4} {'Layer':<20} {'CX(m)':<10} {'CY(m)':<10} {'W(cm)':<8} {'H(cm)':<8} {'Solids':<6}")
    print(f"  {'-'*4} {'-'*20} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*6}")
    for i, pg in enumerate(pillar_groups):
        print(f"  {i+1:<4} {pg['layer']:<20} "
              f"{to_real(pg['cx']):<10} {to_real(pg['cy']):<10} "
              f"{round(pg['w'] * SCALE * 100, 1):<8} {round(pg['h'] * SCALE * 100, 1):<8} "
              f"{pg['n_solids']:<6}")

    # ── 3. TEXT entities ────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("3. TEXT ENTITIES (labels)")
    print("=" * 80)

    texts = [e for e in all_entities if e.dxftype() in ("TEXT", "MTEXT")]
    print(f"  Total TEXT/MTEXT in file: {len(texts)}")

    beams = []
    slabs = []
    pillars_txt = []
    other_texts = []

    for t in texts:
        if t.dxftype() == "TEXT":
            txt = t.dxf.text.strip()
            x, y = t.dxf.insert[0], t.dxf.insert[1]
        else:  # MTEXT
            txt = t.text.strip() if hasattr(t, 'text') else t.dxf.text.strip()
            x, y = t.dxf.insert[0], t.dxf.insert[1]

        if not txt:
            continue

        record = {"text": txt, "x": x, "y": y, "layer": t.dxf.layer, "in_plan": in_plan(x, y)}

        # Beam labels: V followed by number, possibly with letter suffix
        if re.match(r'^V\d', txt, re.IGNORECASE):
            beams.append(record)
        # Slab labels
        elif re.match(r'^L\d', txt, re.IGNORECASE):
            slabs.append(record)
        # Pillar labels
        elif re.match(r'^P\d', txt, re.IGNORECASE):
            pillars_txt.append(record)
        else:
            other_texts.append(record)

    print(f"\n  --- BEAM labels (V...) : {len(beams)} ---")
    beams.sort(key=lambda r: r["text"])
    for b in beams:
        flag = "*" if b["in_plan"] else " "
        print(f"  {flag} {b['text']:<25} layer={b['layer']:<20} "
              f"pos=({to_real(b['x']):.2f}, {to_real(b['y']):.2f})m")

    print(f"\n  --- SLAB labels (L...) : {len(slabs)} ---")
    slabs.sort(key=lambda r: r["text"])
    for s in slabs:
        flag = "*" if s["in_plan"] else " "
        print(f"  {flag} {s['text']:<25} layer={s['layer']:<20} "
              f"pos=({to_real(s['x']):.2f}, {to_real(s['y']):.2f})m")

    print(f"\n  --- PILLAR labels (P...) : {len(pillars_txt)} ---")
    pillars_txt.sort(key=lambda r: r["text"])
    for p in pillars_txt:
        flag = "*" if p["in_plan"] else " "
        print(f"  {flag} {p['text']:<25} layer={p['layer']:<20} "
              f"pos=({to_real(p['x']):.2f}, {to_real(p['y']):.2f})m")

    # Show a sample of other texts in plan area
    other_in_plan = [t for t in other_texts if t["in_plan"]]
    print(f"\n  --- Other TEXT in plan area: {len(other_in_plan)} (showing first 40) ---")
    for t in other_in_plan[:40]:
        print(f"    {t['text']:<30} layer={t['layer']:<20} "
              f"pos=({to_real(t['x']):.2f}, {to_real(t['y']):.2f})m")

    # ── 4. LINE entities ───────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("4. LINE ENTITIES in plan area")
    print("=" * 80)

    lines = [e for e in all_entities if e.dxftype() == "LINE"]
    print(f"  Total LINEs in file: {len(lines)}")

    h_lines = []  # horizontal
    v_lines = []  # vertical
    d_lines = []  # diagonal

    for ln in lines:
        x1, y1 = ln.dxf.start[0], ln.dxf.start[1]
        x2, y2 = ln.dxf.end[0], ln.dxf.end[1]
        # Check if at least one endpoint is in plan area
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        if not in_plan(mx, my):
            continue

        layer = ln.dxf.layer
        if abs(y1 - y2) < TOL:  # horizontal
            h_lines.append({
                "y": (y1 + y2) / 2,
                "x_min": min(x1, x2), "x_max": max(x1, x2),
                "layer": layer,
            })
        elif abs(x1 - x2) < TOL:  # vertical
            v_lines.append({
                "x": (x1 + x2) / 2,
                "y_min": min(y1, y2), "y_max": max(y1, y2),
                "layer": layer,
            })
        else:
            d_lines.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "layer": layer,
            })

    print(f"  In plan area: {len(h_lines)} horizontal, {len(v_lines)} vertical, {len(d_lines)} diagonal")

    # Group horizontal lines by Y coordinate
    print(f"\n  --- Horizontal lines grouped by Y ---")
    h_lines.sort(key=lambda l: l["y"])
    h_groups = []
    for hl in h_lines:
        placed = False
        for g in h_groups:
            if abs(g["y"] - hl["y"]) < TOL:
                g["lines"].append(hl)
                g["x_min"] = min(g["x_min"], hl["x_min"])
                g["x_max"] = max(g["x_max"], hl["x_max"])
                placed = True
                break
        if not placed:
            h_groups.append({
                "y": hl["y"],
                "x_min": hl["x_min"], "x_max": hl["x_max"],
                "lines": [hl],
            })

    h_groups.sort(key=lambda g: g["y"])
    # Show by layer breakdown
    layer_h_counts = defaultdict(int)
    for hl in h_lines:
        layer_h_counts[hl["layer"]] += 1

    print(f"  H-lines per layer: {dict(layer_h_counts)}")
    print(f"  Unique Y positions: {len(h_groups)}")
    print(f"  {'Y(m)':<12} {'X_min(m)':<12} {'X_max(m)':<12} {'Span(m)':<10} {'Count':<6} {'Layers'}")
    for g in h_groups:
        layers = set(l["layer"] for l in g["lines"])
        print(f"  {to_real(g['y']):<12} {to_real(g['x_min']):<12} {to_real(g['x_max']):<12} "
              f"{to_real(g['x_max'] - g['x_min']):<10} {len(g['lines']):<6} {layers}")

    # Group vertical lines by X coordinate
    print(f"\n  --- Vertical lines grouped by X ---")
    v_lines.sort(key=lambda l: l["x"])
    v_groups = []
    for vl in v_lines:
        placed = False
        for g in v_groups:
            if abs(g["x"] - vl["x"]) < TOL:
                g["lines"].append(vl)
                g["y_min"] = min(g["y_min"], vl["y_min"])
                g["y_max"] = max(g["y_max"], vl["y_max"])
                placed = True
                break
        if not placed:
            v_groups.append({
                "x": vl["x"],
                "y_min": vl["y_min"], "y_max": vl["y_max"],
                "lines": [vl],
            })

    v_groups.sort(key=lambda g: g["x"])
    layer_v_counts = defaultdict(int)
    for vl in v_lines:
        layer_v_counts[vl["layer"]] += 1

    print(f"  V-lines per layer: {dict(layer_v_counts)}")
    print(f"  Unique X positions: {len(v_groups)}")
    print(f"  {'X(m)':<12} {'Y_min(m)':<12} {'Y_max(m)':<12} {'Span(m)':<10} {'Count':<6} {'Layers'}")
    for g in v_groups:
        layers = set(l["layer"] for l in g["lines"])
        print(f"  {to_real(g['x']):<12} {to_real(g['y_min']):<12} {to_real(g['y_max']):<12} "
              f"{to_real(g['y_max'] - g['y_min']):<10} {len(g['lines']):<6} {layers}")

    # ── 5. Beam edge detection ──────────────────────────────────────────
    print("\n" + "=" * 80)
    print("5. BEAM EDGE DETECTION (parallel line pairs)")
    print("=" * 80)

    # Common beam widths in DXF units (cm / 100 * 50 scale factor... no:
    # real_cm / 100 = meters, meters / 0.5 = DXF units
    # 14cm beam: 0.14m / 0.5 = 0.28 DXF units
    # 20cm beam: 0.20m / 0.5 = 0.40 DXF units
    # 12cm beam: 0.12m / 0.5 = 0.24 DXF units
    beam_widths_dxf = {
        0.24: "12cm",
        0.28: "14cm",
        0.30: "15cm",
        0.40: "20cm",
        0.50: "25cm",
    }

    print("\n  --- Horizontal beam pairs (two H-lines close in Y) ---")
    h_beam_pairs = []
    for i in range(len(h_groups)):
        for j in range(i + 1, len(h_groups)):
            dy = abs(h_groups[j]["y"] - h_groups[i]["y"])
            # Check overlap in X
            overlap_min = max(h_groups[i]["x_min"], h_groups[j]["x_min"])
            overlap_max = min(h_groups[i]["x_max"], h_groups[j]["x_max"])
            if overlap_max - overlap_min < 0.5:  # need some overlap
                continue
            for bw_dxf, bw_label in beam_widths_dxf.items():
                if abs(dy - bw_dxf) < BEAM_WIDTH_TOL:
                    h_beam_pairs.append({
                        "y1": h_groups[i]["y"],
                        "y2": h_groups[j]["y"],
                        "x_min": overlap_min,
                        "x_max": overlap_max,
                        "width": bw_label,
                        "dy_dxf": dy,
                    })

    h_beam_pairs.sort(key=lambda p: (p["y1"], p["x_min"]))
    print(f"  Found {len(h_beam_pairs)} horizontal beam-edge pairs")
    for bp in h_beam_pairs:
        print(f"    Y={to_real(bp['y1']):.2f}-{to_real(bp['y2']):.2f}m  "
              f"X={to_real(bp['x_min']):.2f}-{to_real(bp['x_max']):.2f}m  "
              f"width={bp['width']}  (dy_dxf={bp['dy_dxf']:.3f})")

    print("\n  --- Vertical beam pairs (two V-lines close in X) ---")
    v_beam_pairs = []
    for i in range(len(v_groups)):
        for j in range(i + 1, len(v_groups)):
            dx = abs(v_groups[j]["x"] - v_groups[i]["x"])
            overlap_min = max(v_groups[i]["y_min"], v_groups[j]["y_min"])
            overlap_max = min(v_groups[i]["y_max"], v_groups[j]["y_max"])
            if overlap_max - overlap_min < 0.5:
                continue
            for bw_dxf, bw_label in beam_widths_dxf.items():
                if abs(dx - bw_dxf) < BEAM_WIDTH_TOL:
                    v_beam_pairs.append({
                        "x1": v_groups[i]["x"],
                        "x2": v_groups[j]["x"],
                        "y_min": overlap_min,
                        "y_max": overlap_max,
                        "width": bw_label,
                        "dx_dxf": dx,
                    })

    v_beam_pairs.sort(key=lambda p: (p["x1"], p["y_min"]))
    print(f"  Found {len(v_beam_pairs)} vertical beam-edge pairs")
    for bp in v_beam_pairs:
        print(f"    X={to_real(bp['x1']):.2f}-{to_real(bp['x2']):.2f}m  "
              f"Y={to_real(bp['y_min']):.2f}-{to_real(bp['y_max']):.2f}m  "
              f"width={bp['width']}  (dx_dxf={bp['dx_dxf']:.3f})")

    # ── 6. SOLID vertex dump (for debugging) ───────────────────────────
    print("\n" + "=" * 80)
    print("6. RAW SOLID VERTEX DATA (first 20 pillar groups)")
    print("=" * 80)
    for i, pg in enumerate(pillar_groups[:20]):
        print(f"\n  Pillar group #{i+1}: layer={pg['layer']}  "
              f"bbox=({to_real(pg['x_min']):.3f},{to_real(pg['y_min']):.3f})-"
              f"({to_real(pg['x_max']):.3f},{to_real(pg['y_max']):.3f})m  "
              f"size={round(pg['w']*SCALE*100,1)}x{round(pg['h']*SCALE*100,1)}cm")

    # ── 7. Dimension entities (DIMENSION) ──────────────────────────────
    print("\n" + "=" * 80)
    print("7. DIMENSION ENTITIES")
    print("=" * 80)
    dims = [e for e in all_entities if e.dxftype() == "DIMENSION"]
    print(f"  Total DIMENSION entities: {len(dims)}")
    for d in dims[:20]:
        try:
            txt = d.dxf.text if d.dxf.text else "(auto)"
            dp = d.dxf.defpoint if hasattr(d.dxf, 'defpoint') else "?"
            print(f"    text={txt:<15} layer={d.dxf.layer:<20} defpoint={dp}")
        except Exception:
            pass

    # ── 8. INSERT (block references) ───────────────────────────────────
    print("\n" + "=" * 80)
    print("8. INSERT (block references) in plan area")
    print("=" * 80)
    inserts = [e for e in all_entities if e.dxftype() == "INSERT"]
    print(f"  Total INSERTs: {len(inserts)}")
    insert_names = defaultdict(int)
    for ins in inserts:
        insert_names[ins.dxf.name] += 1
    for name, count in sorted(insert_names.items()):
        print(f"    {name:<30} count={count}")

    plan_inserts = []
    for ins in inserts:
        x, y = ins.dxf.insert[0], ins.dxf.insert[1]
        if in_plan(x, y):
            plan_inserts.append(ins)
    print(f"\n  INSERTs in plan area: {len(plan_inserts)}")
    for ins in plan_inserts[:30]:
        print(f"    name={ins.dxf.name:<25} pos=({to_real(ins.dxf.insert[0]):.2f}, {to_real(ins.dxf.insert[1]):.2f})m  layer={ins.dxf.layer}")

    # ── 9. LWPOLYLINE / POLYLINE ───────────────────────────────────────
    print("\n" + "=" * 80)
    print("9. POLYLINE / LWPOLYLINE entities")
    print("=" * 80)
    polys = [e for e in all_entities if e.dxftype() in ("LWPOLYLINE", "POLYLINE")]
    print(f"  Total: {len(polys)}")
    for p in polys[:15]:
        try:
            if p.dxftype() == "LWPOLYLINE":
                pts = list(p.get_points())
                n = len(pts)
                layer = p.dxf.layer
                closed = p.closed
            else:
                pts = [(v.dxf.location[0], v.dxf.location[1]) for v in p.vertices]
                n = len(pts)
                layer = p.dxf.layer
                closed = p.is_closed
            print(f"    {p.dxftype():<15} layer={layer:<20} pts={n} closed={closed}")
            if n <= 8:
                for pt in pts:
                    print(f"      ({to_real(pt[0]):.3f}, {to_real(pt[1]):.3f})m")
        except Exception as ex:
            print(f"    Error reading polyline: {ex}")

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Pillar groups (SOLID):    {len(pillar_groups)}")
    print(f"  Beam labels (V...):       {len(beams)}")
    print(f"  Slab labels (L...):       {len(slabs)}")
    print(f"  Pillar labels (P...):     {len(pillars_txt)}")
    print(f"  H-line groups:            {len(h_groups)}")
    print(f"  V-line groups:            {len(v_groups)}")
    print(f"  H-beam edge pairs:        {len(h_beam_pairs)}")
    print(f"  V-beam edge pairs:        {len(v_beam_pairs)}")
    print(f"  Diagonal lines in plan:   {len(d_lines)}")


if __name__ == "__main__":
    main()
