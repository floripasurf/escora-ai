"""Check circulation topology: can every room be reached without passing through a bedroom?"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.layout.shape_grammar import generate_layout

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

TOLERANCE = 0.02  # 2cm tolerance for adjacency check


def rooms_adjacent(a, b):
    """Check if two rooms share an edge (not just a corner)."""
    ax0, ay0 = a["rel_x"], a["rel_y"]
    ax1, ay1 = ax0 + a["rel_w"], ay0 + a["rel_h"]
    bx0, by0 = b["rel_x"], b["rel_y"]
    bx1, by1 = bx0 + b["rel_w"], by0 + b["rel_h"]

    # Horizontal overlap (for vertical adjacency)
    h_overlap = min(ax1, bx1) - max(ax0, bx0)
    # Vertical overlap (for horizontal adjacency)
    v_overlap = min(ay1, by1) - max(ay0, by0)

    # Vertically adjacent (top-bottom): share horizontal edge
    if h_overlap > TOLERANCE:
        if abs(ay1 - by0) < TOLERANCE or abs(by1 - ay0) < TOLERANCE:
            return True

    # Horizontally adjacent (left-right): share vertical edge
    if v_overlap > TOLERANCE:
        if abs(ax1 - bx0) < TOLERANCE or abs(bx1 - ax0) < TOLERANCE:
            return True

    return False


def check_circulation(template):
    """BFS from entrance (living room) through non-bedroom rooms.

    Returns list of rooms that can ONLY be reached by passing through a bedroom.
    """
    rooms = template["rooms"]

    # Build adjacency graph
    n = len(rooms)
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if rooms_adjacent(rooms[i], rooms[j]):
                adj[i].add(j)
                adj[j].add(i)

    # Find living room (entrance)
    start = None
    for i, r in enumerate(rooms):
        if r["type"] == "living":
            start = i
            break

    if start is None:
        return [], adj, rooms

    # BFS: reach rooms WITHOUT passing through bedrooms
    # We can traverse through any non-bedroom room
    visited = set()
    queue = [start]
    visited.add(start)

    while queue:
        current = queue.pop(0)
        for neighbor in adj[current]:
            if neighbor not in visited:
                # We can ENTER any room, but only TRAVERSE through non-bedrooms
                # A bedroom is a destination, not a corridor
                visited.add(neighbor)
                if rooms[neighbor]["type"] != "bedroom":
                    # Can continue traversing through this room
                    queue.append(neighbor)

    # Find unreachable rooms (not visited at all)
    unreachable = []
    for i, r in enumerate(rooms):
        if i not in visited:
            unreachable.append(r["name"])

    # Also check: rooms reachable ONLY through a bedroom
    # BFS allowing only non-bedroom traversal already handles this
    # If a room is visited, it was reached without traversing a bedroom

    return unreachable, adj, rooms


def print_adjacency(rooms, adj):
    """Print adjacency list for debugging."""
    for i, r in enumerate(rooms):
        neighbors = [rooms[j]["name"] for j in sorted(adj[i])]
        print(f"  {r['name']:15s} → {', '.join(neighbors)}")


def main():
    print("=" * 70)
    print("ANÁLISE DE CIRCULAÇÃO — Acessibilidade sem passar por quartos")
    print("=" * 70)

    all_ok = True

    for label, bed, area, lt, gar, ban in CONFIGS:
        t = generate_layout(bed, area, lt, gar, ban)
        unreachable, adj, rooms = check_circulation(t)

        if unreachable:
            all_ok = False
            print(f"\n✗ {label}: PROBLEMA — cômodos inacessíveis sem passar por quarto:")
            for name in unreachable:
                print(f"    → {name}")
            print(f"  Grafo de adjacência:")
            print_adjacency(rooms, adj)
        else:
            print(f"✓ {label}: OK")

    print(f"\n{'=' * 70}")
    if all_ok:
        print("RESULTADO: Todos os cômodos acessíveis sem passar por quartos.")
    else:
        print("RESULTADO: Problemas de circulação encontrados!")

    # Detailed adjacency for configs with wet core stacking
    print(f"\n{'=' * 70}")
    print("DETALHE: Adjacência em configs com wet core empilhado")
    print("=" * 70)

    for label, bed, area, lt, gar, ban in CONFIGS:
        if ban > 1 or lt == "separate_kitchen":
            t = generate_layout(bed, area, lt, gar, ban)
            _, adj, rooms = check_circulation(t)
            print(f"\n{label}:")
            print_adjacency(rooms, adj)


if __name__ == "__main__":
    main()
