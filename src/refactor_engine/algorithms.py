"""Pure algorithmic core: O(N) deduplication and risk scoring."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

Record = dict[str, Any]


def dedup_key(rec: Record) -> tuple[str, int, str]:
    """Hashable identity of a transaction: (account, amount, timestamp)."""
    return (rec["account"], rec["amount_cents"], rec["ts"])


def find_duplicates(records: Sequence[Record]) -> tuple[str, ...]:
    """Return ids of the *later* copy of every duplicate, in input order.

    Single pass, O(N) time, O(N) memory, fully deterministic -- replaces
    the legacy O(N^2) pairwise scan.
    """
    seen: set[tuple[str, int, str]] = set()
    dupes: list[str] = []
    for rec in records:
        key = dedup_key(rec)
        if key in seen:
            dupes.append(rec["id"])
        else:
            seen.add(key)
    return tuple(dupes)


def risk_score(amount_cents: int) -> float:
    """Bounded risk score in [0, 1]; 100_00 cents (a $100) maps to 0.01."""
    return min(1.0, abs(amount_cents) / 1_000_000.0)


def aggregate_cents(records: Sequence[Record]) -> int:
    """Exact integer-cent aggregation; float-free by contract."""
    return sum(rec["amount_cents"] for rec in records)
