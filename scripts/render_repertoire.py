"""Render repertoire templates as PNG images for visual validation."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.layout.repertoire import get_all_templates
from src.layout.repertoire.compat import to_legacy_template
from src.layout.repertoire._base import TemplateV2

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    print("pip install matplotlib")
    sys.exit(1)

# Room colors
COLORS = {
    "living": "#FFD54F",
    "bedroom": "#81D4FA",
    "bathroom": "#CE93D8",
    "service": "#A5D6A7",
    "kitchen": "#FFAB91",
    "circulation": "#E0E0E0",
    "garage": "#BCAAA4",
    "varanda": "#FFF9C4",
}

_MIN_AREA = {
    "bedroom": 9.0, "living": 12.0, "kitchen": 4.0,
    "bathroom": 2.25, "service": 2.5, "circulation": 1.5, "garage": 12.0,
    "varanda": 2.0,
}
_MIN_DIM = {
    "bedroom": 3.00, "living": 2.40, "kitchen": 1.80,
    "bathroom": 1.20, "service": 1.50, "circulation": 0.90, "garage": 3.00,
    "varanda": 1.00,
}


def render_template(template: TemplateV2, outdir: str) -> str:
    """Render a TemplateV2 directly from zone geometry."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 8))

    # Compute bounding box
    bb = template.bounding_box
    bb_w = bb[2] - bb[0]
    bb_h = bb[3] - bb[1]
    margin = 1.0

    ax.set_xlim(bb[0] - margin, bb[2] + margin)
    ax.set_ylim(bb[1] - margin, bb[3] + margin)
    ax.set_aspect("equal")
    ax.set_title(
        f"{template.name}\n"
        f"{template.typology} | {template.built_area_m2:.0f}m² construído | "
        f"{template.bedrooms}Q {template.bathrooms}Ban",
        fontsize=11,
    )

    issues = []

    # Draw zones as dashed outlines
    for zone in template.zones:
        style = "--" if zone.is_outdoor else "-"
        color = "#90CAF9" if zone.is_outdoor else "#CFD8DC"
        rect = mpatches.Rectangle(
            (zone.anchor_x, zone.anchor_y), zone.width_m, zone.depth_m,
            fill=True, facecolor=color, edgecolor="gray",
            linewidth=0.5, linestyle=style, alpha=0.3,
        )
        ax.add_patch(rect)
        # Zone label
        ax.text(
            zone.anchor_x + zone.width_m / 2,
            zone.anchor_y + zone.depth_m + 0.15,
            f"[{zone.id}]",
            ha="center", fontsize=6, color="gray", fontstyle="italic",
        )

    # Draw rooms
    for room in template.rooms:
        zone = template.get_zone(room.zone_id)
        if zone is None:
            continue

        rx = zone.anchor_x + room.rel_x * zone.width_m
        ry = zone.anchor_y + room.rel_y * zone.depth_m
        rw = room.rel_w * zone.width_m
        rh = room.rel_h * zone.depth_m
        area = rw * rh
        min_side = min(rw, rh)
        rtype = room.type

        color = COLORS.get(rtype, "#F5F5F5")

        # Check violations
        has_issue = False
        if rtype in _MIN_AREA and area < _MIN_AREA[rtype] - 0.1:
            has_issue = True
            issues.append(f"{room.name}: {area:.1f}m² < {_MIN_AREA[rtype]}m² mín")
        if rtype in _MIN_DIM and min_side < _MIN_DIM[rtype] - 0.05:
            has_issue = True
            issues.append(f"{room.name}: dim {min_side:.2f}m < {_MIN_DIM[rtype]}m mín")

        ec = "red" if has_issue else "black"
        lw = 2.5 if has_issue else 1.0

        rect = mpatches.Rectangle(
            (rx, ry), rw, rh,
            facecolor=color, edgecolor=ec, linewidth=lw, alpha=0.85,
        )
        ax.add_patch(rect)

        # Label
        cx = rx + rw / 2
        cy = ry + rh / 2
        fontsize = 7 if rw < 2.0 or rh < 2.0 else 8
        ax.text(cx, cy + 0.15, room.name,
                ha="center", va="center", fontsize=fontsize, fontweight="bold")
        ax.text(cx, cy - 0.25, f"{rw:.1f}×{rh:.1f}m\n{area:.1f}m²",
                ha="center", va="center", fontsize=6, color="#555")

    # Building outline (non-outdoor zones only)
    indoor_zones = [z for z in template.zones if not z.is_outdoor]
    if indoor_zones:
        ix0 = min(z.anchor_x for z in indoor_zones)
        iy0 = min(z.anchor_y for z in indoor_zones)
        ix1 = max(z.anchor_x + z.width_m for z in indoor_zones)
        iy1 = max(z.anchor_y + z.depth_m for z in indoor_zones)
        # Draw each indoor zone outline
        for z in indoor_zones:
            ax.add_patch(mpatches.Rectangle(
                (z.anchor_x, z.anchor_y), z.width_m, z.depth_m,
                fill=False, edgecolor="black", linewidth=2,
            ))

    # Street label
    ax.text(bb[0] + bb_w / 2, bb[1] - 0.5, "← RUA →",
            ha="center", fontsize=9, color="brown", fontweight="bold")

    # Issues box
    if issues:
        issue_text = "PROBLEMAS:\n" + "\n".join(issues)
        ax.text(0.02, 0.98, issue_text, transform=ax.transAxes,
                fontsize=7, va="top", ha="left",
                bbox=dict(boxstyle="round", facecolor="#FFCDD2", alpha=0.9),
                color="red")

    # Circulation graph
    circ = template.circulation
    circ_text = "Circulação:\n"
    for src, dsts in circ.edges.items():
        if dsts:
            circ_text += f"  {src} → {', '.join(dsts)}\n"
    ax.text(0.98, 0.02, circ_text, transform=ax.transAxes,
            fontsize=6, va="bottom", ha="right",
            bbox=dict(boxstyle="round", facecolor="#E8F5E9", alpha=0.8),
            family="monospace")

    # Tags
    ax.text(0.02, 0.02, " ".join(f"[{t}]" for t in template.tags),
            transform=ax.transAxes, fontsize=6, va="bottom", ha="left",
            color="gray")

    # Legend
    handles = []
    for rtype, color in COLORS.items():
        handles.append(mpatches.Patch(facecolor=color, edgecolor="black", label=rtype))
    ax.legend(handles=handles, loc="upper right", fontsize=6, framealpha=0.8)

    ax.set_xlabel("Largura (m)")
    ax.set_ylabel("Profundidade (m)")
    ax.grid(True, alpha=0.2)

    path = os.path.join(outdir, f"{template.id}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path, issues


def main():
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "output", "repertoire_renders")
    os.makedirs(outdir, exist_ok=True)

    templates = get_all_templates()
    print(f"Rendering {len(templates)} templates from repertoire...")

    all_issues = {}
    for t in templates:
        path, issues = render_template(t, outdir)
        status = "✓" if not issues else "✗"
        print(f"  {status} {path}")
        if issues:
            all_issues[t.id] = issues

    print(f"\n{'=' * 60}")
    print(f"Total: {len(templates)} templates, {len(all_issues)} with issues")
    if all_issues:
        print(f"\nIssues:")
        for tid, issues in all_issues.items():
            print(f"  {tid}:")
            for i in issues:
                print(f"    - {i}")


if __name__ == "__main__":
    main()
