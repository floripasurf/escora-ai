"""Batch test — run sketch_reader on all images in Plantas/ folder."""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from src.drawing.sketch_reader import read_sketch_to_dxf, read_sketch

PLANTAS_DIR = Path(__file__).resolve().parent.parent / "Plantas"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "sketch_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def main():
    images = sorted(
        f for f in PLANTAS_DIR.iterdir()
        if f.suffix.lower() in IMAGE_EXTS
    )

    if not images:
        print(f"No images found in {PLANTAS_DIR}")
        return

    print(f"Found {len(images)} images in {PLANTAS_DIR}")
    print("=" * 60)

    results = []

    for img_path in images:
        name = img_path.stem
        out_dxf = OUTPUT_DIR / f"{name}.dxf"
        print(f"\n  Processing: {img_path.name}")

        try:
            model = read_sketch(str(img_path), scale_reference_m=7.0)
            walls = len(model.walls)
            bb = model.bounding_box
            w = bb[2] - bb[0]
            d = bb[3] - bb[1]

            saved = read_sketch_to_dxf(
                str(img_path),
                str(out_dxf),
                scale_reference_m=7.0,
            )

            status = "OK"
            detail = f"{walls} walls, {w:.1f}x{d:.1f}m"
            print(f"    -> {status}: {detail}")
            print(f"    -> Saved: {saved}")

        except Exception as e:
            status = "FAIL"
            detail = str(e)
            walls = 0
            print(f"    -> {status}: {detail}")

        results.append({
            "image": img_path.name,
            "status": status,
            "walls": walls,
            "detail": detail,
        })

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    ok = sum(1 for r in results if r["status"] == "OK")
    fail = sum(1 for r in results if r["status"] == "FAIL")

    for r in results:
        icon = "v" if r["status"] == "OK" else "X"
        print(f"  [{icon}] {r['image']:50s} {r['detail']}")

    print(f"\n  {ok}/{len(results)} succeeded, {fail} failed")
    print(f"  Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
