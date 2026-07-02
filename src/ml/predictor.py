"""ML predictor for shoring decisions.

Loads trained models and provides predictions that augment
the rule-based engine in the pipeline.

Usage:
    predictor = ShoringPredictor.load()
    prediction = predictor.predict_support_type(beam_features)
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import numpy as np

try:
    import joblib
except ImportError:
    joblib = None  # ML predictions disabled — rule-based engine used instead

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"

SUPPORT_LABELS = {0: "none", 1: "telescopic", 2: "tower"}
EQUIPMENT_LABELS = {0: "none", 1: "VM130", 2: "VM80"}


@dataclass
class ShoringPrediction:
    """ML prediction for a structural beam's shoring needs."""
    support_type: str  # 'none', 'telescopic', 'tower'
    support_confidence: float
    recommended_spacing_m: Optional[float] = None
    recommended_equipment: Optional[str] = None  # 'VM130', 'VM80', None
    equipment_confidence: float = 0.0

    # Probabilities for each class
    support_probabilities: Dict[str, float] = None

    @property
    def is_confident(self) -> bool:
        """True if prediction confidence is high enough to use."""
        return self.support_confidence >= 0.6


class ShoringPredictor:
    """Loads trained models and predicts shoring decisions."""

    def __init__(self):
        self.support_clf = None
        self.spacing_reg = None
        self.equipment_clf = None
        self._loaded = False

    @classmethod
    def load(cls, model_dir: Optional[str] = None) -> "ShoringPredictor":
        """Load trained models from disk.

        Returns a predictor instance. If models don't exist, returns
        an unloaded predictor that always returns None.
        """
        predictor = cls()
        model_path = Path(model_dir) if model_dir else MODEL_DIR

        try:
            support_path = model_path / "support_type_clf.joblib"
            if support_path.exists():
                predictor.support_clf = joblib.load(str(support_path))
                logger.info(f"Loaded support type classifier from {support_path}")

            spacing_path = model_path / "spacing_reg.joblib"
            if spacing_path.exists():
                predictor.spacing_reg = joblib.load(str(spacing_path))
                logger.info(f"Loaded spacing regressor from {spacing_path}")

            equipment_path = model_path / "equipment_clf.joblib"
            if equipment_path.exists():
                predictor.equipment_clf = joblib.load(str(equipment_path))
                logger.info(f"Loaded equipment recommender from {equipment_path}")

            predictor._loaded = any([
                predictor.support_clf,
                predictor.spacing_reg,
                predictor.equipment_clf,
            ])
        except Exception as e:
            logger.warning(f"Failed to load ML models: {e}")

        return predictor

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def _build_features(
        self,
        beam_length_m: float,
        beam_angle_deg: float,
        nearest_pillar_dist_m: float,
        pillar_count_3m: int,
        nearby_beam_count: int,
        nearby_beam_avg_length_m: float,
        is_perimeter: bool,
    ) -> np.ndarray:
        """Build feature vector matching training format."""
        return np.array([[
            beam_length_m,
            beam_angle_deg,
            nearest_pillar_dist_m,
            pillar_count_3m,
            nearby_beam_count,
            nearby_beam_avg_length_m,
            1.0 if is_perimeter else 0.0,
        ]])

    def predict(
        self,
        beam_length_m: float,
        beam_angle_deg: float = 0.0,
        nearest_pillar_dist_m: float = 99.0,
        pillar_count_3m: int = 0,
        nearby_beam_count: int = 0,
        nearby_beam_avg_length_m: float = 0.0,
        is_perimeter: bool = False,
    ) -> Optional[ShoringPrediction]:
        """Predict shoring decision for a structural beam.

        Returns None if models are not loaded.
        """
        if not self._loaded:
            return None

        X = self._build_features(
            beam_length_m, beam_angle_deg, nearest_pillar_dist_m,
            pillar_count_3m, nearby_beam_count, nearby_beam_avg_length_m,
            is_perimeter,
        )

        # Support type prediction
        support_type = "none"
        confidence = 0.0
        probabilities = {}
        if self.support_clf is not None:
            proba = self.support_clf.predict_proba(X)[0]
            pred_idx = int(np.argmax(proba))
            support_type = SUPPORT_LABELS.get(pred_idx, "none")
            confidence = float(proba[pred_idx])
            probabilities = {
                SUPPORT_LABELS[i]: float(p)
                for i, p in enumerate(proba)
                if i in SUPPORT_LABELS
            }

        # Spacing prediction
        spacing = None
        if self.spacing_reg is not None and support_type != "none":
            spacing = float(self.spacing_reg.predict(X)[0])
            spacing = max(0.3, min(spacing, 3.0))  # Clamp to reasonable range

        # Equipment prediction
        equipment = None
        equip_conf = 0.0
        if self.equipment_clf is not None:
            proba = self.equipment_clf.predict_proba(X)[0]
            pred_idx = int(np.argmax(proba))
            equip_label = EQUIPMENT_LABELS.get(pred_idx, "none")
            equip_conf = float(proba[pred_idx])
            if equip_label != "none":
                equipment = equip_label

        return ShoringPrediction(
            support_type=support_type,
            support_confidence=confidence,
            recommended_spacing_m=round(spacing, 2) if spacing else None,
            recommended_equipment=equipment,
            equipment_confidence=equip_conf,
            support_probabilities=probabilities,
        )

    def predict_batch(
        self,
        beams: List[Dict[str, Any]],
    ) -> List[Optional[ShoringPrediction]]:
        """Predict shoring for multiple beams at once.

        Each beam dict should have keys matching predict() parameters.
        """
        return [
            self.predict(**beam)
            for beam in beams
        ]
