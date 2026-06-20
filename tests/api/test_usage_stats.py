"""Telemetria de piloto: agregação dos jobs existentes (sem tabela nova)."""

from datetime import datetime, timedelta

from api.services.usage_stats import summarize_jobs


def _job(status, created, updated, results=None):
    return {
        "status": status,
        "created_at": created,
        "updated_at": updated,
        "results_data": results,
    }


def test_summarize_empty():
    s = summarize_jobs([])
    assert s["total"] == 0
    assert s["error_rate"] == 0.0
    assert s["avg_elapsed_seconds"] is None
    assert s["requires_review"] == 0


def test_summarize_counts_status_and_error_rate():
    base = datetime(2026, 6, 20, 12, 0, 0)
    jobs = [
        _job("done", base, base + timedelta(seconds=30)),
        _job("done", base, base + timedelta(seconds=90)),
        _job("error", base, base + timedelta(seconds=5)),
        _job("processing", base, base),
    ]
    s = summarize_jobs(jobs)
    assert s["total"] == 4
    assert s["by_status"]["done"] == 2
    assert s["by_status"]["error"] == 1
    assert s["by_status"]["processing"] == 1
    assert s["error_rate"] == 0.25
    # avg elapsed só dos done: (30 + 90) / 2 = 60
    assert s["avg_elapsed_seconds"] == 60.0


def test_summarize_counts_requires_review():
    base = datetime(2026, 6, 20, 12, 0, 0)
    jobs = [
        _job("done", base, base, results={"requires_review": True}),
        _job("done", base, base, results={"requires_review": False}),
        _job("done", base, base, results=None),
    ]
    s = summarize_jobs(jobs)
    assert s["requires_review"] == 1
