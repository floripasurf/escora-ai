"""DXF visual inspector — render DXF to PNG and dump a layer/entity summary.

Usage:
    python3 scripts/dxf_inspector.py render <dxf_path> [--out <png_path>]
    python3 scripts/dxf_inspector.py summary <dxf_path> [--out <json_path>]
    python3 scripts/dxf_inspector.py compare <our_dxf> <supplier_dxf> [--out <png_path>]

The goal is to give Claude a feedback loop on the generated output by:
  1. Rendering the DXF to PNG (readable via the Read tool)
  2. Dumping a per-layer entity/color/bbox summary (JSON)
  3. Producing a side-by-side PNG against an Supplier reference file
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend


def _upgrade_if_old(doc):
    # ezdxf rendering needs ≥ R2000 for LWPOLYLINE etc.
    if doc.dxfversion < "AC1015":
        doc.dxfversion = "AC1015"
    return doc


def render_dxf(dxf_path: str, png_path: str, dpi: int = 200) -> str:
    doc = ezdxf.readfile(dxf_path)
    _upgrade_if_old(doc)
    msp = doc.modelspace()

    fig = plt.figure(figsize=(16, 12), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_aspect("equal")
    ax.set_axis_off()

    ctx = RenderContext(doc)
    backend = MatplotlibBackend(ax)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png_path


def summarize_dxf(dxf_path: str) -> Dict[str, Any]:
    doc = ezdxf.readfile(dxf_path)
    _upgrade_if_old(doc)
    msp = doc.modelspace()

    layer_info: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"entity_types": Counter(), "count": 0,
                 "color": None, "bbox": None}
    )

    # per-layer color from layer table
    for layer in doc.layers:
        layer_info[layer.dxf.name]["color"] = layer.dxf.color

    overall_bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]

    def _expand(bbox, x, y):
        bbox[0] = min(bbox[0], x)
        bbox[1] = min(bbox[1], y)
        bbox[2] = max(bbox[2], x)
        bbox[3] = max(bbox[3], y)

    for e in msp:
        layer = e.dxf.layer
        etype = e.dxftype()
        info = layer_info[layer]
        info["entity_types"][etype] += 1
        info["count"] += 1

        lb = info["bbox"]
        if lb is None:
            lb = [float("inf"), float("inf"), float("-inf"), float("-inf")]
            info["bbox"] = lb

        try:
            if etype == "LINE":
                _expand(lb, e.dxf.start.x, e.dxf.start.y)
                _expand(lb, e.dxf.end.x, e.dxf.end.y)
                _expand(overall_bbox, e.dxf.start.x, e.dxf.start.y)
                _expand(overall_bbox, e.dxf.end.x, e.dxf.end.y)
            elif etype == "LWPOLYLINE":
                for x, y, *_ in e.get_points("xyb"):
                    _expand(lb, x, y)
                    _expand(overall_bbox, x, y)
            elif etype == "CIRCLE":
                cx, cy = e.dxf.center.x, e.dxf.center.y
                r = e.dxf.radius
                _expand(lb, cx - r, cy - r)
                _expand(lb, cx + r, cy + r)
                _expand(overall_bbox, cx - r, cy - r)
                _expand(overall_bbox, cx + r, cy + r)
            elif etype in ("TEXT", "MTEXT"):
                p = e.dxf.insert
                _expand(lb, p.x, p.y)
                _expand(overall_bbox, p.x, p.y)
        except Exception:
            pass

    # serialize
    layers_out = {}
    for name, info in layer_info.items():
        bbox = info["bbox"]
        if bbox and bbox[0] != float("inf"):
            bbox_out = [round(v, 3) for v in bbox]
        else:
            bbox_out = None
        layers_out[name] = {
            "count": info["count"],
            "color": info["color"],
            "entity_types": dict(info["entity_types"]),
            "bbox": bbox_out,
        }

    return {
        "file": dxf_path,
        "dxf_version": doc.dxfversion,
        "total_entities": sum(i["count"] for i in layer_info.values()),
        "layer_count": len(layers_out),
        "bbox": [round(v, 3) for v in overall_bbox] if overall_bbox[0] != float("inf") else None,
        "layers": dict(sorted(layers_out.items(),
                              key=lambda kv: -kv[1]["count"])),
    }


def compare_dxfs(our_dxf: str, supplier_dxf: str, png_path: str, dpi: int = 180) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(24, 12), dpi=dpi)
    for ax, path, title in (
        (axes[0], our_dxf, f"OUR: {Path(our_dxf).name}"),
        (axes[1], supplier_dxf, f"SUPPLIER: {Path(supplier_dxf).name}"),
    ):
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(title, fontsize=10)
        doc = ezdxf.readfile(path)
        _upgrade_if_old(doc)
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)

    fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png_path


def _default_out(dxf_path: str, suffix: str) -> str:
    p = Path(dxf_path)
    out_dir = Path("data/output/inspector")
    out_dir.mkdir(parents=True, exist_ok=True)
    return str(out_dir / (p.stem + suffix))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render")
    r.add_argument("dxf")
    r.add_argument("--out", default=None)
    r.add_argument("--dpi", type=int, default=200)

    s = sub.add_parser("summary")
    s.add_argument("dxf")
    s.add_argument("--out", default=None)

    c = sub.add_parser("compare")
    c.add_argument("our_dxf")
    c.add_argument("supplier_dxf")
    c.add_argument("--out", default=None)
    c.add_argument("--dpi", type=int, default=180)

    args = ap.parse_args(argv)

    if args.cmd == "render":
        out = args.out or _default_out(args.dxf, ".png")
        path = render_dxf(args.dxf, out, dpi=args.dpi)
        print(path)
    elif args.cmd == "summary":
        summary = summarize_dxf(args.dxf)
        if args.out:
            Path(args.out).write_text(json.dumps(summary, indent=2))
            print(args.out)
        else:
            json.dump(summary, sys.stdout, indent=2)
            print()
    elif args.cmd == "compare":
        out = args.out or _default_out(args.our_dxf, "_vs_supplier.png")
        path = compare_dxfs(args.our_dxf, args.supplier_dxf, out, dpi=args.dpi)
        print(path)


if __name__ == "__main__":
    main()
