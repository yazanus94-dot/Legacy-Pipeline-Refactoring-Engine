"""Unit tests for the refactored engine's pure functions."""

from __future__ import annotations

import pytest

from refactor_engine import (
    aggregate_cents,
    chunks,
    enrich_all,
    find_duplicates,
    parse_records,
    risk_score,
    synthesize_dataset,
)
from refactor_engine.exceptions import RecordError


class TestParseRecords:
    def test_normalization_to_cents(self) -> None:
        raw = [{"id": "1", "account": "a", "amount": 12.34, "ts": "t"}]
        (rec,) = list(parse_records(raw))
        assert rec["amount_cents"] == 1234

    def test_strict_mode_raises(self) -> None:
        raw = [{"id": "1", "account": "a", "ts": "t"}]
        with pytest.raises(RecordError):
            list(parse_records(raw))

    def test_lenient_mode_continues(self) -> None:
        raw = [
            {"id": "1", "account": "a", "amount": 1.0, "ts": "t"},
            {"id": "2", "account": "a", "ts": "t"},
            {"id": "3", "account": "a", "amount": 2.0, "ts": "t"},
        ]
        errors: list[RecordError] = []
        records = list(parse_records(raw, on_error=errors.append))
        assert len(records) == 2 and len(errors) == 1

    def test_non_numeric_amount_rejected(self) -> None:
        raw = [{"id": "1", "account": "a", "amount": "abc", "ts": "t"}]
        with pytest.raises(RecordError):
            list(parse_records(raw))


class TestFindDuplicates:
    def test_later_copy_flagged(self) -> None:
        records = [
            {"id": "a", "account": "x", "amount_cents": 100, "ts": "t1"},
            {"id": "b", "account": "x", "amount_cents": 100, "ts": "t1"},
            {"id": "c", "account": "x", "amount_cents": 100, "ts": "t1"},
        ]
        assert find_duplicates(records) == ("b", "c")

    def test_distinct_same_amount_different_ts(self) -> None:
        records = [
            {"id": "a", "account": "x", "amount_cents": 100, "ts": "t1"},
            {"id": "b", "account": "x", "amount_cents": 100, "ts": "t2"},
        ]
        assert find_duplicates(records) == ()

    def test_empty_input(self) -> None:
        assert find_duplicates([]) == ()


class TestAggregation:
    def test_negative_amounts(self) -> None:
        records = [{"amount_cents": -500}, {"amount_cents": 1500}]
        assert aggregate_cents(records) == 1000

    def test_empty(self) -> None:
        assert aggregate_cents([]) == 0


class TestChunks:
    def test_exact_chunks(self) -> None:
        records = list(range(8))
        assert [len(c) for c in chunks(records, 3)] == [3, 3, 2]

    def test_invalid_size(self) -> None:
        with pytest.raises(ValueError):
            list(chunks([1], 0))


class TestEnrichment:
    def test_order_preserved_despite_concurrency(self) -> None:
        records = [{"id": str(i), "account": "a", "amount_cents": i * 10, "ts": "t"} for i in range(50)]
        out = enrich_all(records, concurrency=16, latency_s=0.001)
        assert [r["id"] for r in out] == [str(i) for i in range(50)]
        assert all(0.0 <= r["risk_score"] <= 1.0 for r in out)


class TestRiskScore:
    def test_bounds(self) -> None:
        assert risk_score(0) == 0.0
        assert risk_score(10**9) == 1.0

    def test_linear_region(self) -> None:
        assert risk_score(1_000_000) == 1.0
        assert risk_score(100) == 0.0001


class TestSynthesizeDataset:
    def test_deterministic(self) -> None:
        assert synthesize_dataset(100) == synthesize_dataset(100)

    def test_duplicates_injected(self) -> None:
        raw = synthesize_dataset(500, duplicate_rate=0.2, seed=7)
        # The dedup key must collide for injected rows: count exact repeats.
        keys = [(r["account"], round(r["amount"], 2), r["ts"]) for r in raw]
        assert len(keys) != len(set(keys))
