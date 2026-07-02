"""Train ML models on engineer reference data.

Trains three models:
1. Support Type Classifier — tower vs telescopic vs none
2. Spacing Regressor — predict optimal shore spacing
3. Equipment Recommender — predict distribution beam model (VM130/VM80/none)

Uses scikit-learn with RandomForest/GradientBoosting.
Models are saved as joblib files for inference in the pipeline.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score, LeaveOneGroupOut

try:
    import joblib
except ImportError:
    from sklearn.externals import joblib

from src.ml.feature_extractor import (
    extract_training_data, examples_to_arrays,
)

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"
TRAINING_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "training" / "sergio1_extracted.json"


def train_support_type_classifier(
    examples: list,
    model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a classifier to predict support type (none/telescopic/tower).

    Uses Leave-One-File-Out cross-validation to estimate generalization.
    """
    X, y, feature_names = examples_to_arrays(examples)

    # Group by file for LOGO cross-validation
    files = [e.file_name for e in examples]
    unique_files = sorted(set(files))
    groups = np.array([unique_files.index(f) for f in files])

    logger.info(f"Training support type classifier: {len(X)} samples, {len(unique_files)} files")
    logger.info(f"  Class distribution: none={sum(y==0)}, telescopic={sum(y==1)}, tower={sum(y==2)}")

    # Train model
    clf = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )

    # Cross-validation (leave-one-file-out)
    if len(unique_files) >= 3:
        logo = LeaveOneGroupOut()
        cv_scores = cross_val_score(clf, X, y, cv=logo, groups=groups, scoring="accuracy")
        logger.info(f"  LOGO CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
        logger.info(f"  Per-file scores: {[f'{s:.3f}' for s in cv_scores]}")
    else:
        cv_scores = np.array([0.0])
        logger.info("  Skipping CV (< 3 files)")

    # Train final model on all data
    clf.fit(X, y)

    # Feature importance
    importances = dict(zip(feature_names, clf.feature_importances_))
    sorted_imp = sorted(importances.items(), key=lambda x: -x[1])
    logger.info("  Feature importances:")
    for name, imp in sorted_imp:
        logger.info(f"    {name}: {imp:.3f}")

    # Save model
    if model_path is None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        model_path = str(MODEL_DIR / "support_type_clf.joblib")
    joblib.dump(clf, model_path)
    logger.info(f"  Model saved: {model_path}")

    return {
        "model_path": model_path,
        "n_samples": len(X),
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "feature_importances": importances,
        "cv_accuracy_mean": float(cv_scores.mean()),
        "cv_accuracy_std": float(cv_scores.std()),
        "class_distribution": {
            "none": int(sum(y == 0)),
            "telescopic": int(sum(y == 1)),
            "tower": int(sum(y == 2)),
        },
    }


def train_spacing_regressor(
    examples: list,
    model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a regressor to predict optimal shore spacing (meters).

    Only trains on examples where shore_count > 0.
    """
    # Filter to examples with actual shoring
    shored = [e for e in examples if e.shore_count > 0 and e.avg_spacing_m > 0]

    if len(shored) < 10:
        logger.warning(f"Too few shored examples ({len(shored)}) for spacing regressor")
        return {"error": "insufficient_data", "n_samples": len(shored)}

    X, _, feature_names = examples_to_arrays(shored)
    y_spacing = np.array([e.avg_spacing_m for e in shored])

    logger.info(f"Training spacing regressor: {len(X)} samples")
    logger.info(f"  Spacing range: {y_spacing.min():.2f} - {y_spacing.max():.2f} m")
    logger.info(f"  Spacing mean: {y_spacing.mean():.2f} m")

    reg = GradientBoostingRegressor(
        n_estimators=80,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
    )

    # Simple CV
    from sklearn.model_selection import cross_val_score
    cv_scores = cross_val_score(reg, X, y_spacing, cv=min(5, len(shored)), scoring="r2")
    logger.info(f"  CV R²: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    reg.fit(X, y_spacing)

    if model_path is None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        model_path = str(MODEL_DIR / "spacing_reg.joblib")
    joblib.dump(reg, model_path)
    logger.info(f"  Model saved: {model_path}")

    return {
        "model_path": model_path,
        "n_samples": len(X),
        "cv_r2_mean": float(cv_scores.mean()),
        "cv_r2_std": float(cv_scores.std()),
        "spacing_range": [float(y_spacing.min()), float(y_spacing.max())],
        "spacing_mean": float(y_spacing.mean()),
    }


def train_equipment_recommender(
    examples: list,
    model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a classifier to recommend distribution beam model.

    Classes: 'none', 'VM130', 'VM80'
    """
    X, _, feature_names = examples_to_arrays(examples)

    label_map = {"": 0, "VM130": 1, "VM80": 2}
    y = np.array([label_map.get(e.dist_beam_model, 0) for e in examples])

    logger.info(f"Training equipment recommender: {len(X)} samples")
    logger.info(f"  Class distribution: none={sum(y==0)}, VM130={sum(y==1)}, VM80={sum(y==2)}")

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=4,
        random_state=42,
    )

    cv_scores = cross_val_score(clf, X, y, cv=min(5, len(X)), scoring="accuracy")
    logger.info(f"  CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    clf.fit(X, y)

    if model_path is None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        model_path = str(MODEL_DIR / "equipment_clf.joblib")
    joblib.dump(clf, model_path)
    logger.info(f"  Model saved: {model_path}")

    return {
        "model_path": model_path,
        "n_samples": len(X),
        "cv_accuracy_mean": float(cv_scores.mean()),
        "class_distribution": {
            "none": int(sum(y == 0)),
            "VM130": int(sum(y == 1)),
            "VM80": int(sum(y == 2)),
        },
    }


def train_all(data_path: Optional[str] = None) -> Dict[str, Any]:
    """Train all models and return summary.

    Args:
        data_path: Path to sergio1_extracted.json. Uses default if None.

    Returns:
        Dictionary with results for each model.
    """
    if data_path is None:
        data_path = str(TRAINING_DATA_PATH)

    logger.info(f"Loading training data from {data_path}")
    examples = extract_training_data(data_path)

    if not examples:
        return {"error": "no_training_data"}

    logger.info(f"Total training examples: {len(examples)}")

    results = {}
    results["support_type"] = train_support_type_classifier(examples)
    results["spacing"] = train_spacing_regressor(examples)
    results["equipment"] = train_equipment_recommender(examples)

    # Save training summary
    summary_path = str(MODEL_DIR / "training_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Training summary saved: {summary_path}")

    return results
