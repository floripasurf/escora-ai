"""Render shape grammar layouts as PNG images for visual analysis."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.layout.shape_grammar import generate_layout

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
}

CONFIGS = [
    ("01_1Q_45m2", 1, 45, "open_kitchen", False, 1),
    ("02_2Q_55m2", 2, 55, "open_kitchen", False, 1),
    ("03_2Q_2ban_55m2", 2, 55, "open_kitchen", False, 2),
    ("04_3Q_65m2", 3, 65, "open_kitchen", False, 1),
    ("05_3Q_gar_70m2", 3, 70, "open_kitchen", True, 1),
    ("06_2Q_gar_60m2", 2, 60, "open_kitchen", True, 1),
    ("07_3Q_gar_2ban_85m2", 3, 85, "open_kitchen", True, 2),
    ("08_2Q_sep_55m2", 2, 55, "separate_kitchen", False, 1),
    ("09_1Q_35m2", 1, 35, "open_kitchen", False, 1),
    ("10_2Q_sep_gar_65m2", 2, 65, "separate_kitchen", True, 1),
    ("11_3Q_2ban_75m2", 3, 75, "open_kitchen", False, 2),
    ("12_1Q_sep_40m2", 1, 40, "separate_kitchen", False, 1),
]

_MIN_AREA = {
    "bedroom": 8.0, "living": 12.0, "kitchen": 4.0,
    "bathroom": 2.4, "service": 2.5, "circulation": 1.5, "garage": 12.0,
}
_MIN_DIM = {
    "bedroom": 2.40, "living": 2.40, "kitchen": 1.80,
    "bathroom": 1.50, "service": 1.50, "circulation": 0.90, "garage": 3.00,
}


def render(template, label, outdir):
    w = template["preferred_width_m"]
    d = template["preferred_depth_m"]

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    ax.set_xlim(-0.5, w + 0.5)
    ax.set_ylim(-0.5, d + 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"{label}\n{w:.1f}m × {d:.1f}m = {w*d:.0f}m²", fontsize=11)

    # Draw building outline
    ax.add_patch(mpatches.Rectangle((0, 0), w, d, fill=False,
                                     edgecolor="black", linewidth=2))

    issues = []

    for room in template["rooms"]:
        rx = room["rel_x"] * w
        ry = room["rel_y"] * d
        rw = room["rel_w"] * w
        rh = room["rel_h"] * d
        area = rw * rh
        min_side = min(rw, rh)
        rtype = room["type"]

        color = COLORS.get(rtype, "#F5F5F5")

        # Check violations
        has_issue = False
        if rtype in _MIN_AREA and area < _MIN_AREA[rtype] - 0.1:
            has_issue = True
            issues.append(f"{room['name']}: {area:.1f}m² < {_MIN_AREA[rtype]}m² mín")
        if rtype in _MIN_DIM and min_side < _MIN_DIM[rtype] - 0.05:
            has_issue = True
            issues.append(f"{room['name']}: dim {min_side:.2f}m < {_MIN_DIM[rtype]}m mín")

        # Red border for violations
        ec = "red" if has_issue else "black"
        lw = 2.5 if has_issue else 1.0

        rect = mpatches.Rectangle((rx, ry), rw, rh,
                                   facecolor=color, edgecolor=ec,
                                   linewidth=lw, alpha=0.85)
        ax.add_patch(rect)

        # Label
        cx = rx + rw / 2
        cy = ry + rh / 2
        fontsize = 7 if rw < 2.0 or rh < 2.0 else 8
        ax.text(cx, cy + 0.15, room["name"],
                ha="center", va="center", fontsize=fontsize, fontweight="bold")
        ax.text(cx, cy - 0.25, f"{rw:.1f}×{rh:.1f}m\n{area:.1f}m²",
                ha="center", va="center", fontsize=6, color="#555")

    # Dimension annotations
    ax.annotate("", xy=(w, -0.3), xytext=(0, -0.3),
                arrowprops=dict(arrowstyle="<->", color="gray"))
    ax.text(w / 2, -0.45, f"{w:.1f}m", ha="center", fontsize=8, color="gray")

    ax.annotate("", xy=(-0.3, d), xytext=(-0.3, 0),
                arrowprops=dict(arrowstyle="<->", color="gray"))
    ax.text(-0.45, d / 2, f"{d:.1f}m", ha="center", fontsize=8,
            color="gray", rotation=90)

    # Street label
    ax.text(w / 2, -0.15, "← RUA →", ha="center", fontsize=9,
            color="brown", fontweight="bold")

    # Issues box
    if issues:
        issue_text = "PROBLEMAS:\n" + "\n".join(issues)
        ax.text(0.02, 0.98, issue_text, transform=ax.transAxes,
                fontsize=7, va="top", ha="left",
                bbox=dict(boxstyle="round", facecolor="#FFCDD2", alpha=0.9),
                color="red")

    # Legend
    handles = []
    for rtype, color in COLORS.items():
        handles.append(mpatches.Patch(facecolor=color, edgecolor="black",
                                       label=rtype))
    ax.legend(handles=handles, loc="upper right", fontsize=6,
              framealpha=0.8)

    ax.set_xlabel("Largura (m)")
    ax.set_ylabel("Profundidade (m)")
    ax.grid(True, alpha=0.2)

    path = os.path.join(outdir, f"{label}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path, issues


def main():
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "output", "layout_renders")
    os.makedirs(outdir, exist_ok=True)

    all_issues = {}
    for label, bed, area, lt, gar, ban in CONFIGS:
        t = generate_layout(bed, area, lt, gar, ban)
        path, issues = render(t, label, outdir)
        print(f"{'✓' if not issues else '✗'} {path}")
        if issues:
            all_issues[label] = issues

    print(f"\n{'='*60}")
    print(f"Total: {len(CONFIGS)} layouts, {len(all_issues)} with issues")
    if all_issues:
        print(f"\nIssues found:")
        for label, issues in all_issues.items():
            print(f"  {label}:")
            for i in issues:
                print(f"    - {i}")


if __name__ == "__main__":
    main()
