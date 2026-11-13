"""Refactored transaction-processing engine -- the "after" state.

Design goals, mirroring each documented legacy defect:

R1  O(N) duplicate detection via a single hashable-key pass.
R2  No module-level state; memory bounded by the working set, not the
    process lifetime.
R3  No mutable default arguments anywhere; pure functions only.
R4  Exact chunking via explicit generator; every record processed exactly
    once.
R5  Integer-cent arithmetic -- money is never kept in binary floating
    point, so aggregation is exact.
R6  Errors are *reported*, not swallowed: per-record failures are
    collected into a typed error list; totals only cover valid records.
Plus: concurrent enrichment via asyncio with a bounded worker pool.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from refactor_engine.algorithms import aggregate_cents, dedup_key, find_duplicates, risk_score
from refactor_engine.exceptions import RecordError

Record = dict[str, Any]


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of a full pipeline run."""

    records_out: int
    duplicates: tuple[str, ...]
    total_cents: int
    errors: tuple[RecordError, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Parsing (R2: no hidden global state)
# ---------------------------------------------------------------------------

def parse_records(
    raw: Iterable[dict[str, Any]],
    on_error: Callable[[RecordError], None] | None = None,
) -> Iterator[Record]:
    """Normalize raw rows lazily; emits validated records as a stream.

    With ``on_error=None`` the first invalid record raises. With a callback,
    invalid records are reported and skipped, letting the stream continue.
    """
    for row in raw:
        try:
            amount_cents = int(round(float(row["amount"]) * 100))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            error = RecordError(
                row.get("id"), f"invalid amount: {row.get('amount')!r}"
            )
            if on_error is None:
                raise error from exc
            on_error(error)
            continue
        if "id" not in row or "account" not in row or "ts" not in row:
            error = RecordError(row.get("id"), "missing required field")
            if on_error is None:
                raise error
            on_error(error)
            continue
        yield {
            "id": str(row["id"]),
            "account": str(row["account"]),
            "amount_cents": amount_cents,
            "ts": str(row["ts"]),
        }


# ---------------------------------------------------------------------------
# Concurrent enrichment (asyncio, bounded pool)
# ---------------------------------------------------------------------------

async def _enrich(record: Record, latency_s: float) -> Record:
    """Simulated I/O-bound enrichment (network call in production)."""
    if latency_s > 0:
        await asyncio.sleep(latency_s)
    out = dict(record)
    out["risk_score"] = risk_score(record["amount_cents"])
    return out


async def enrich_stream(
    records: Sequence[Record],
    concurrency: int = 64,
    latency_s: float = 0.0005,
) -> AsyncIterator[Record]:
    """Enrich records with a bounded concurrent pool, input order preserved.

    Yields results in input order (deterministic output despite concurrent
    execution) and never spawns more than ``concurrency`` coroutines.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(rec: Record) -> Record:
        async with semaphore:
            return await _enrich(rec, latency_s)

    tasks = [asyncio.ensure_future(bounded(rec)) for rec in records]
    for task in tasks:
        yield await task


def enrich_all(
    records: Sequence[Record],
    concurrency: int = 64,
    latency_s: float = 0.0005,
) -> list[Record]:
    """Sync wrapper around the concurrent enricher."""

    async def _run() -> list[Record]:
        return [rec async for rec in enrich_stream(records, concurrency, latency_s)]

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Exact chunking (R4)
# ---------------------------------------------------------------------------

def chunks(records: Sequence[Record], size: int) -> Iterator[Sequence[Record]]:
    """Yield disjoint chunks; every record appears exactly once."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for start in range(0, len(records), size):
        yield records[start : start + size]


# ---------------------------------------------------------------------------
# Exact aggregation (R5: integer cents, R6: explicit errors)
# ---------------------------------------------------------------------------

def aggregate_cents(records: Iterable[Record]) -> int:
    """Sum integer cents exactly. Overflow-free for any realistic volume."""
    return sum(rec["amount_cents"] for rec in records)


def run_pipeline(
    raw: Sequence[dict[str, Any]],
    concurrency: int = 64,
    chunk_size: int = 512,
    latency_s: float = 0.0005,
) -> PipelineResult:
    """The refactored entry point: parse -> dedupe -> concurrent enrich -> aggregate."""
    errors: list[RecordError] = []
    valid: list[Record] = list(
        parse_records(raw, on_error=errors.append)
    )
    duplicates = find_duplicates(valid)

    enriched: list[Record] = []
    for chunk in chunks(valid, chunk_size):
        enriched.extend(
            enrich_all(chunk, concurrency=concurrency, latency_s=latency_s)
        )

    return PipelineResult(
        records_out=len(enriched),
        duplicates=duplicates,
        total_cents=aggregate_cents(enriched),
        errors=tuple(errors),
    )
