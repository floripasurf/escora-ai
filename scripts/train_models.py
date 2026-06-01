"""Train ML models from engineer reference data.

Usage:
    python3 scripts/train_models.py
    python3 scripts/train_models.py --data data/training/sergio1_extracted.json
"""

import sys
import json
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

from src.ml.trainer import train_all


def main():
    parser = argparse.ArgumentParser(description="Train Escora.AI ML models")
    parser.add_argument(
        "--data", type=str, default=None,
        help="Path to extracted training data JSON",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ESCORA.AI — ML Model Training")
    print("=" * 60)

    results = train_all(data_path=args.data)

    print("\n" + "=" * 60)
    print("  TRAINING RESULTS")
    print("=" * 60)

    if "error" in results:
        print(f"\n  ERROR: {results['error']}")
        return

    # Support type classifier
    st = results.get("support_type", {})
    if "error" not in st:
        print(f"\n  Support Type Classifier:")
        print(f"    Samples: {st.get('n_samples', 0)}")
        print(f"    CV Accuracy: {st.get('cv_accuracy_mean', 0):.1%} ± {st.get('cv_accuracy_std', 0):.1%}")
        print(f"    Classes: {st.get('class_distribution', {})}")
        print(f"    Top features:")
        imps = st.get("feature_importances", {})
        for name, imp in sorted(imps.items(), key=lambda x: -x[1])[:5]:
            print(f"      {name}: {imp:.3f}")

    # Spacing regressor
    sp = results.get("spacing", {})
    if "error" not in sp:
        print(f"\n  Spacing Regressor:")
        print(f"    Samples: {sp.get('n_samples', 0)}")
        print(f"    CV R²: {sp.get('cv_r2_mean', 0):.3f} ± {sp.get('cv_r2_std', 0):.3f}")
        print(f"    Spacing range: {sp.get('spacing_range', [])}")
    else:
        print(f"\n  Spacing Regressor: {sp.get('error', 'unknown error')}")

    # Equipment recommender
    eq = results.get("equipment", {})
    if "error" not in eq:
        print(f"\n  Equipment Recommender:")
        print(f"    Samples: {eq.get('n_samples', 0)}")
        print(f"    CV Accuracy: {eq.get('cv_accuracy_mean', 0):.1%}")
        print(f"    Classes: {eq.get('class_distribution', {})}")

    print(f"\n  Models saved to: data/models/")
    print("=" * 60)


if __name__ == "__main__":
    main()
