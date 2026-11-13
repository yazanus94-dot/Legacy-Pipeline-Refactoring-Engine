"""LEGACY transaction pipeline -- the deliberately flawed "before" state.

DO NOT USE IN PRODUCTION. This module is preserved exactly as received so
that the refactored engine under ``src/`` can be benchmarked against it and
the bug-fix regression tests can prove the documented defects.

Documented defects (each has a repro test in tests/):

D1  O(N^2) duplicate detection -- pairwise scan of the full record list.
D2  Unbounded module-level cache -- grows with every run, never cleared
    (classic Python memory leak; keeps every record alive forever).
D3  Mutable default argument -- the ``seen`` list of ``flag_duplicates``
    leaks state *between calls*.
D4  Off-by-one in chunking -- ``range(0, n, size)`` with ``records[start
    : start + size + 1]`` drops the final partial chunk and re-processes
    one record at every chunk boundary.
D5  Float accumulation -- running totals in binary floating point drift
    by up to ~1e-9 per addend on large inputs.
D6  Silent exception swallowing -- a failing record inside the aggregation
    loop is caught and ignored, corrupting totals without any signal.
"""

from __future__ import annotations

import time
from typing import Any

# D2: module-level cache that is never cleared
_RECORD_CACHE: list[dict[str, Any]] = []


def parse_records(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize raw rows; appends every parsed record to the global cache (D2)."""
    parsed = []
    for row in raw:
        rec = {
            "id": row["id"],
            "account": row["account"],
            "amount": float(row["amount"]),
            "ts": row["ts"],
        }
        parsed.append(rec)
        _RECORD_CACHE.append(rec)  # D2: leak
    return parsed


def parse_records_fixed(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same normalization without the global cache side effect.

    Kept next to the legacy function so the benchmark can isolate the
    allocation cost of the leak.
    """
    return [
        {"id": row["id"], "account": row["account"], "amount": float(row["amount"]), "ts": row["ts"]}
        for row in raw
    ]


def flag_duplicates(records: list[dict[str, Any]], dupes: list[str] | None = None) -> list[str]:
    """D3 + D1: O(N^2) scan seeded by a mutable default argument."""
    if dupes is None:
        dupes = []  # never reached when callers pass the leaked list back
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if (
                records[i]["account"] == records[j]["account"]
                and records[i]["amount"] == records[j]["amount"]
                and records[i]["ts"] == records[j]["ts"]
            ):
                if records[j]["id"] not in dupes:
                    dupes.append(records[j]["id"])
    return dupes


def _enrich_simulated(record: dict[str, Any]) -> dict[str, Any]:
    """Simulate a slow per-record I/O enrichment (network call in real life)."""
    time.sleep(0.0005)  # 0.5 ms per record, synchronous
    out = dict(record)
    out["risk_score"] = min(1.0, abs(record["amount"]) / 10_000.0)
    return out


def process_chunks(records: list[dict[str, Any]], size: int = 512) -> list[dict[str, Any]]:
    """D4: chunk boundaries double-count one record per chunk.

    ``records[start : start + size + 1]`` grabs one record *beyond* the
    chunk, and the next chunk starts on that same record again. Every
    chunk boundary therefore contributes a duplicated enriched record,
    inflating ``records_out`` and the aggregated total by exactly
    ``len(records) // size`` records. A partial final chunk is fine, but
    nobody notices the duplication because the "extra" records are valid
    transformations of real input.
    """
    out: list[dict[str, Any]] = []
    for start in range(0, len(records), size):
        chunk = records[start : start + size + 1]  # D4: one extra record
        for rec in chunk:
            out.append(_enrich_simulated(rec))
    return out


def aggregate(records: list[dict[str, Any]], total: float = 0.0) -> float:
    """D5 + D6: float accumulation and silent exception swallowing."""
    for rec in records:
        try:
            total += rec["amount"]  # D5
        except Exception:  # D6: swallow and continue
            continue
    return total


def run_pipeline(raw: list[dict[str, Any]]) -> dict[str, Any]:
    """The legacy entry point: parse -> dedupe -> chunk/enrich -> aggregate."""
    parsed = parse_records(raw)
    dupes = flag_duplicates(parsed)  # fresh call, but O(N^2) cost (D1)
    enriched = process_chunks(parsed)
    total = aggregate(enriched)
    return {"records_out": len(enriched), "duplicates": dupes, "total": total}
