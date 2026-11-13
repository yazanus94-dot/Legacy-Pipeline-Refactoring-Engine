"""Integration tests: legacy vs refactored on realistic datasets."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LEGACY_DIR = Path(__file__).resolve().parents[2] / "legacy"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import pipeline_v1 as legacy  # noqa: E402

from refactor_engine import synthesize_dataset, run_pipeline  # noqa: E402


@pytest.fixture(scope="module")
def dataset():
    return synthesize_dataset(600, duplicate_rate=0.05, seed=99)


class TestDivergence:
    """The two engines must *disagree* exactly where the legacy bugs bite."""

    def test_refactored_output_count_is_exact(self, dataset) -> None:
        result = run_pipeline(dataset, latency_s=0.0)
        assert result.records_out == 600  # every record exactly once

    def test_legacy_output_count_inflated_by_boundaries(self, dataset) -> None:
        legacy_out = legacy.run_pipeline(dataset)
        # 600 records / 512 chunk size = 1 boundary -> 1 duplicated record
        assert legacy_out["records_out"] == 601

    def test_refactored_total_is_exact_sum(self, dataset) -> None:
        result = run_pipeline(dataset, latency_s=0.0)
        expected = sum(int(round(float(r["amount"]) * 100)) for r in dataset)
        assert result.total_cents == expected

    def test_duplicate_counts_agree(self, dataset) -> None:
        legacy_out = legacy.run_pipeline(dataset)
        result = run_pipeline(dataset, latency_s=0.0)
        assert len(legacy_out["duplicates"]) == len(result.duplicates)


class TestEndToEnd:
    def test_corrupt_rows_are_reported_not_swallowed(self) -> None:
        raw = synthesize_dataset(100, missing_amount_every=25)
        result = run_pipeline(raw, latency_s=0.0)
        assert len(result.errors) == 4
        assert result.records_out == 96

    def test_clean_run_has_no_errors(self, dataset) -> None:
        result = run_pipeline(dataset, latency_s=0.0)
        assert result.errors == ()

    def test_concurrency_parameter_accepted(self, dataset) -> None:
        small = run_pipeline(dataset[:100], concurrency=8, latency_s=0.0)
        big = run_pipeline(dataset[:100], concurrency=64, latency_s=0.0)
        assert small.total_cents == big.total_cents
