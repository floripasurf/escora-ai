"""Tests for consumption rate warnings (Supplier rule A6, Q8).

Locadora: "12-16 kg/m³ é a faixa usual". Two warning levels:
- Fora de 8-20 kg/m³: critical warning (inputs likely wrong).
- Dentro de 8-20 mas fora de 12-16: soft warning (outside usual range).
"""
from src.output.report_data import (
    ConsumptionByHeightRow,
    _consumption_rate_warnings,
)


def _row(rate: float) -> ConsumptionByHeightRow:
    return ConsumptionByHeightRow(
        pe_direito_m=2.80,
        area_m2=100.0,
        volume_bruto_m3=280.0,
        volume_liquido_m3=275.0,
        shores_weight_kg=3000.0,
        accessories_weight_kg=200.0,
        total_weight_kg=3200.0,
        rate_kg_m3_bruto=rate,
        rate_kg_m3_liquido=rate + 0.1,
        rate_kg_m2=rate * 2.8,
        category_label="Laje",
    )


class TestConsumptionRateWarnings:
    def test_rate_in_usual_range_no_warning(self):
        rows = [_row(13.5)]
        warnings = _consumption_rate_warnings(rows)
        assert warnings == []

    def test_rate_boundary_usual_range_no_warning(self):
        # 12.0 e 16.0 dentro da faixa — sem warning
        assert _consumption_rate_warnings([_row(12.0)]) == []
        assert _consumption_rate_warnings([_row(16.0)]) == []

    def test_rate_between_8_and_12_soft_warning(self):
        warnings = _consumption_rate_warnings([_row(10.5)])
        assert len(warnings) == 1
        assert "fora da faixa usual" in warnings[0].lower()
        assert "12-16" in warnings[0]

    def test_rate_between_16_and_20_soft_warning(self):
        warnings = _consumption_rate_warnings([_row(18.0)])
        assert len(warnings) == 1
        assert "fora da faixa usual" in warnings[0].lower()

    def test_rate_below_8_critical_warning(self):
        warnings = _consumption_rate_warnings([_row(5.0)])
        assert len(warnings) == 1
        assert "verificar inputs" in warnings[0].lower()
        assert "fora do esperado" in warnings[0].lower()

    def test_rate_above_20_critical_warning(self):
        warnings = _consumption_rate_warnings([_row(25.0)])
        assert len(warnings) == 1
        assert "verificar inputs" in warnings[0].lower()

    def test_rate_zero_skipped(self):
        """Taxa 0 (sem volume) não gera warning."""
        assert _consumption_rate_warnings([_row(0.0)]) == []

    def test_multiple_rows_multiple_warnings(self):
        rows = [_row(13.5), _row(5.0), _row(17.0)]
        warnings = _consumption_rate_warnings(rows)
        # Uma crítica + uma suave = 2 warnings
        assert len(warnings) == 2
