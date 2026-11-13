"""Reproduction tests for each documented legacy defect.

Every test here pins a defect the refactored engine fixes. They are named
after the defect IDs from ``legacy/pipeline_v1.py`` and
``docs/debugging-log.md`` so documentation, code and evidence stay in sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LEGACY_DIR = Path(__file__).resolve().parents[2] / "legacy"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import pipeline_v1 as legacy  # noqa: E402

from refactor_engine import find_duplicates, parse_records  # noqa: E402


class TestD1QuadraticDedup:
    def test_legacy_duplicate_flags_are_correct_but_slow(self) -> None:
        records = [
            {"id": "a", "account": "x", "amount": 1.0, "ts": "t1"},
            {"id": "b", "account": "x", "amount": 1.0, "ts": "t1"},
            {"id": "c", "account": "y", "amount": 2.0, "ts": "t2"},
        ]
        assert legacy.flag_duplicates(records) == ["b"]

    def test_refactored_matches_on_pairs(self) -> None:
        records = [
            {"id": "a", "account": "x", "amount_cents": 100, "ts": "t1"},
            {"id": "b", "account": "x", "amount_cents": 100, "ts": "t1"},
            {"id": "c", "account": "y", "amount_cents": 200, "ts": "t2"},
        ]
        assert find_duplicates(records) == ("b",)

    def test_refactored_is_linear(self) -> None:
        """Scaling check: doubling N must roughly double, not quadruple, time."""
        import time

        from refactor_engine import synthesize_dataset

        def cost(n: int) -> float:
            records = [
                {
                    "id": f"t{i}",
                    "account": f"a{i % 100}",
                    "amount_cents": i * 3 % 9973,
                    "ts": f"ts{i % 5000}",
                }
                for i in range(n)
            ]
            start = time.perf_counter()
            find_duplicates(records)
            return time.perf_counter() - start

        t_small, t_large = cost(20_000), cost(80_000)
        ratio = t_large / max(t_small, 1e-9)
        assert ratio < 10.0  # linear would be ~4x; quadratic would be ~16x


class TestD2ModuleLevelLeak:
    def test_legacy_cache_grows_forever(self) -> None:
        raw = [{"id": str(i), "account": "a", "amount": 1, "ts": "t"} for i in range(50)]
        legacy.parse_records(raw)
        assert len(legacy._RECORD_CACHE) >= 50  # cached from this very call

    def test_refactored_keeps_no_global_state(self) -> None:
        import refactor_engine.core as core
        import refactor_engine.services as services

        for module in (core, services):
            for name in dir(module):
                if name.startswith("_RECORD"):
                    pytest.fail(f"global cache reintroduced in {module.__name__}.{name}")


class TestD3MutableDefault:
    def test_legacy_state_leaks_between_calls(self) -> None:
        records_a = [
            {"id": "a1", "account": "x", "amount": 1.0, "ts": "t1"},
            {"id": "a2", "account": "x", "amount": 1.0, "ts": "t1"},
        ]
        records_b = [
            {"id": "b1", "account": "y", "amount": 2.0, "ts": "t2"},
            {"id": "b2", "account": "y", "amount": 2.0, "ts": "t2"},
        ]
        first = legacy.flag_duplicates(records_a)
        # Second call reuses *the same list object* as accumulator when the
        # caller passes it back -- the documented real-world failure mode.
        second = legacy.flag_duplicates(records_b, first)
        assert "b2" in second and "a2" in second  # cross-call contamination

    def test_refactored_pure_function(self) -> None:
        records = [
            {"id": "b1", "account": "y", "amount_cents": 200, "ts": "t2"},
            {"id": "b2", "account": "y", "amount_cents": 200, "ts": "t2"},
        ]
        first = find_duplicates(records)
        second = find_duplicates(records)
        assert first == second == ("b2",)


class TestD4BoundaryDuplication:
    def test_legacy_double_counts_boundary_records(self) -> None:
        # 1000 records, chunk size 512: one boundary => exactly 1 duplicate.
        records = [
            {"id": str(i), "account": f"a{i}", "amount": 0.0, "ts": "t"}
            for i in range(1000)
        ]
        out = legacy.process_chunks(records, size=512)
        assert len(out) == 1001  # records[512] processed twice

    def test_refactored_chunks_are_disjoint_and_complete(self) -> None:
        from refactor_engine import chunks

        records = [{"i": i} for i in range(1000)]
        seen: list[int] = []
        for chunk in chunks(records, 512):
            seen.extend(rec["i"] for rec in chunk)
        assert sorted(seen) == list(range(1000))
        assert len(seen) == 1000


class TestD5FloatAccumulation:
    def test_legacy_total_drifts(self) -> None:
        amounts = [{"amount": 0.1} for _ in range(1000)]
        total = legacy.aggregate([{"amount": a["amount"]} for a in amounts])
        # Drift is small (≈1e-12 for 1000 addends) but *nonzero* -- the
        # point is that binary floating point never sums 0.1 exactly,
        # while the refactored engine's integer cents do.
        assert 0 < abs(total - 100.0) < 1e-6

    def test_refactored_total_is_exact(self) -> None:
        from refactor_engine import aggregate_cents

        records = [{"amount_cents": 10} for _ in range(1000)]  # 0.10 USD each
        assert aggregate_cents(records) == 10_000  # exactly $100.00


class TestD6SilentSwallowing:
    def test_legacy_hides_corrupt_records(self) -> None:
        records = [
            {"amount": 1.0},
            {"amount": None},  # None + float raises -> swallowed
            {"amount": 2.0},
        ]
        assert legacy.aggregate(records) == 3.0  # no signal, no error

    def test_refactored_reports_errors(self) -> None:
        from refactor_engine import synthesize_dataset

        raw = synthesize_dataset(30, missing_amount_every=10)
        result = run_pipeline_quiet(raw)
        assert len(result.errors) == 3
        assert all(e.record_id.startswith("tx-") for e in result.errors)


def run_pipeline_quiet(raw: list[dict]) -> object:
    """Helper that runs the refactored pipeline expecting recorded errors."""
    from refactor_engine.services import run_pipeline

    return run_pipeline(raw, latency_s=0.0)
