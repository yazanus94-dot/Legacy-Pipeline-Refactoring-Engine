"""Property-based tests for the refactored engine."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from refactor_engine import (
    aggregate_cents,
    chunks,
    enrich_all,
    find_duplicates,
    parse_records,
)
from refactor_engine.exceptions import RecordError

AMOUNTS = st.floats(
    min_value=-10_000.0, max_value=10_000.0, allow_nan=False, allow_infinity=False
)


@settings(max_examples=75, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=50),      # account
            AMOUNTS,                                     # amount
            st.integers(min_value=0, max_value=1000),    # ts bucket
        ),
        min_size=0,
        max_size=300,
    )
)
def test_dedup_finds_all_repeats(rows: list[tuple[int, float, int]]) -> None:
    """Oracle: brute-force pairwise duplicate detection must agree with O(N)."""
    records = [
        {
            "id": str(i),
            "account": f"a{account}",
            "amount_cents": int(round(amount * 100)),
            "ts": f"t{ts}",
        }
        for i, (account, amount, ts) in enumerate(rows)
    ]
    expected: list[str] = []
    seen: set[tuple[str, int, str]] = set()
    for rec in records:
        key = (rec["account"], rec["amount_cents"], rec["ts"])
        if key in seen:
            expected.append(rec["id"])
        seen.add(key)
    assert find_duplicates(records) == tuple(expected)


@settings(max_examples=75, deadline=None)
@given(st.lists(AMOUNTS, min_size=0, max_size=500))
def test_cents_aggregation_is_exact(amounts: list[float]) -> None:
    """Integer-cent aggregation must equal a Decimal reference sum."""
    from decimal import Decimal

    records = [
        {"amount_cents": int(round(Decimal(str(a)) * 100))} for a in amounts
    ]
    expected = sum(r["amount_cents"] for r in records)
    assert aggregate_cents(records) == expected


@settings(max_examples=50, deadline=None)
@given(
    st.lists(st.integers(), min_size=0, max_size=200),
    st.integers(min_value=1, max_value=37),
)
def test_chunking_preserves_every_record_exactly_once(
    items: list[int], size: int
) -> None:
    seen: list[int] = []
    for chunk in chunks([{"i": i} for i in items], size):
        seen.extend(rec["i"] for rec in chunk)
    assert seen == items


@settings(max_examples=25, deadline=None)
@given(st.lists(AMOUNTS, min_size=1, max_size=40))
def test_concurrent_enrich_preserves_order_and_values(amounts: list[float]) -> None:
    records = [
        {
            "id": str(i),
            "account": "a",
            "amount_cents": int(round(a * 100)),
            "ts": "t",
        }
        for i, a in enumerate(amounts)
    ]
    out = enrich_all(records, concurrency=8, latency_s=0.0002)
    assert [r["id"] for r in out] == [str(i) for i in range(len(records))]
    for original, enriched in zip(records, out, strict=True):
        assert enriched["amount_cents"] == original["amount_cents"]
        assert 0.0 <= enriched["risk_score"] <= 1.0


@settings(max_examples=50, deadline=None)
@given(
    st.lists(
        st.one_of(
            st.just({"bad": True}),
            st.fixed_dictionaries(
                {
                    "id": st.text(max_size=5),
                    "account": st.text(max_size=5),
                    "amount": st.floats(allow_nan=False, allow_infinity=False),
                    "ts": st.text(max_size=5),
                }
            ),
        ),
        min_size=0,
        max_size=50,
    )
)
def test_parse_never_crashes_and_reports_or_yields(raw: list[dict]) -> None:
    """The parser must either yield valid records or report -- never crash."""
    errors: list[RecordError] = []
    records = list(parse_records(raw, on_error=errors.append))
    assert len(records) + len(errors) == len(raw)
