"""Tests for the learning system (Stage 6)."""

import json
import pytest
from pathlib import Path
from src.pipeline.learning_store import LearningStore, LearningRecord
from src.pipeline.stage_learn import extract_learning
from src.models.pipeline_models import (
    PipelineResult, LevelGroup, ClassifiedElement, ElementType,
)
from src.models.calculation_models import CalculationResult


def _element(etype, name=None, width=0.14, height=0.40, score=0.85):
    return ClassifiedElement(
        element_type=etype,
        geometry=[(0, 0), (8, 0)] if etype == ElementType.BEAM else [(0, 0)],
        score_geometric=score, score_textual=0.0, score_final=score,
        name=name, section_width_m=width, section_height_m=height,
        length_m=8.0 if etype == ElementType.BEAM else None,
    )


def _pipeline_result(beams=3, pillars=4, warnings=None):
    elements = (
        [_element(ElementType.BEAM, name=f"V{i+1}") for i in range(beams)]
        + [_element(ElementType.PILLAR, name=f"P{i+1}", width=0.20, height=0.40)
           for i in range(pillars)]
    )
    calc = CalculationResult(
        beam_results=[], slab_results=[], shore_catalog_used=[],
        total_shores=50, total_load_kn=500.0,
        pe_direito_m=2.80, pe_direito_is_default=False,
        warnings=[], validation_errors=[], is_valid=True,
    )
    return PipelineResult(
        filename="TEST.DXF", scale=1.0,
        levels=[LevelGroup(
            level_name="LEVEL1", level_height_m=0.0,
            pe_direito_m=2.80, elements=elements,
        )],
        warnings=warnings or [],
        calculation=calc,
    )


class TestLearningRecord:
    def test_extract_counts(self):
        result = _pipeline_result(beams=5, pillars=3)
        record = extract_learning(result)
        assert record.beam_count == 5
        assert record.pillar_count == 3
        assert record.filename == "TEST.DXF"
        assert record.scale == 1.0

    def test_extract_section_freq(self):
        result = _pipeline_result(beams=3)
        record = extract_learning(result)
        assert "14x40" in record.section_freq
        assert record.section_freq["14x40"] == 3

    def test_extract_scores(self):
        result = _pipeline_result(beams=2, pillars=2)
        record = extract_learning(result)
        assert record.beam_score_avg == pytest.approx(0.85)
        assert record.pillar_score_avg == pytest.approx(0.85)

    def test_extract_warnings(self):
        result = _pipeline_result(warnings=["Aviso 1", "Aviso 2"])
        record = extract_learning(result)
        assert record.warning_count == 2


class TestLearningStore:
    def test_save_and_load(self, tmp_path):
        store_path = tmp_path / "learning.json"
        store = LearningStore(path=store_path)
        assert store.run_count == 0

        result = _pipeline_result()
        record = extract_learning(result)
        store.add(record)
        assert store.run_count == 1

        # Reload from disk
        store2 = LearningStore(path=store_path)
        assert store2.run_count == 1
        assert store2.records[0].filename == "TEST.DXF"

    def test_common_sections(self, tmp_path):
        store = LearningStore(path=tmp_path / "learning.json")
        for _ in range(3):
            record = extract_learning(_pipeline_result(beams=5))
            store.add(record)

        sections = store.get_common_sections()
        assert len(sections) >= 1
        assert sections[0][0] == "14x40"
        assert sections[0][1] == 15  # 5 beams * 3 runs

    def test_default_section_height(self, tmp_path):
        store = LearningStore(path=tmp_path / "learning.json")
        record = extract_learning(_pipeline_result(beams=5))
        store.add(record)

        default_h = store.get_default_section_height()
        assert default_h == pytest.approx(0.40)

    def test_summary(self, tmp_path):
        store = LearningStore(path=tmp_path / "learning.json")
        record = extract_learning(_pipeline_result())
        store.add(record)

        summary = store.summary()
        assert "Total de execuções: 1" in summary
        assert "14x40" in summary

    def test_empty_summary(self, tmp_path):
        store = LearningStore(path=tmp_path / "learning.json")
        assert "Nenhum dado" in store.summary()

    def test_multiple_runs_accumulate(self, tmp_path):
        store = LearningStore(path=tmp_path / "learning.json")

        r1 = extract_learning(_pipeline_result(beams=3, pillars=2))
        r1.filename = "FILE_A.DXF"
        store.add(r1)

        r2 = extract_learning(_pipeline_result(beams=7, pillars=5))
        r2.filename = "FILE_B.DXF"
        store.add(r2)

        assert store.run_count == 2
        summary = store.summary()
        assert "Arquivos processados: 2" in summary
