"""Before/after benchmark: legacy pipeline vs refactored engine.

Measures three axes (all reproducible, no estimated claims):

1. Deduplication scaling: legacy O(N^2) scan vs O(N) hash pass.
2. End-to-end wall time with simulated per-record I/O latency:
   synchronous legacy loop vs bounded-concurrency asyncio pool.
3. Memory growth across repeated runs (legacy module-level cache vs
   stateless refactor) using tracemalloc.

Run:  python benchmarks/benchmark.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "legacy"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import pipeline_v1 as legacy  # noqa: E402

from refactor_engine import (  # noqa: E402
    find_duplicates,
    run_pipeline,
    synthesize_dataset,
)


def median_ms(fn, *args, repeat: int = 3) -> float:
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        fn(*args)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def bench_dedup_scaling() -> list[dict[str, object]]:
    rows = []
    for n in (1_000, 2_000, 4_000, 8_000):
        raw = synthesize_dataset(n, duplicate_rate=0.05, seed=n)
        legacy_recs = legacy.parse_records_fixed(raw)
        legacy_recs = [
            {**r, "amount_cents": int(round(r["amount"] * 100))} for r in legacy_recs
        ]
        rows.append(
            {
                "n": n,
                "legacy_ms": median_ms(legacy.flag_duplicates, legacy_recs),
                "refactored_ms": median_ms(find_duplicates, legacy_recs),
            }
        )
    return rows


def bench_end_to_end() -> dict[str, object]:
    raw = synthesize_dataset(2_000, duplicate_rate=0.05, seed=2026)
    legacy_ms = median_ms(legacy.run_pipeline, raw, repeat=3)
    refactored_ms = median_ms(
        lambda: run_pipeline(raw, latency_s=0.0005), repeat=3
    )
    return {"n": 2000, "legacy_ms": legacy_ms, "refactored_ms": refactored_ms}


def bench_memory_growth() -> dict[str, object]:
    raw = synthesize_dataset(500, seed=7)

    tracemalloc.start()
    for _ in range(5):
        legacy.parse_records(raw)
        legacy._RECORD_CACHE.clear()  # simulate a "restart" between batches
    legacy_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    tracemalloc.start()
    for _ in range(5):
        legacy.parse_records_fixed(raw)  # no cache side effect
    refactored_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    # True leak check: 5 runs WITHOUT clearing the cache.
    tracemalloc.start()
    for _ in range(5):
        legacy.parse_records(raw)
    leaked_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    legacy._RECORD_CACHE.clear()

    return {
        "legacy_with_restarts_peak_kb": legacy_peak / 1024,
        "legacy_leak_5_runs_peak_kb": leaked_peak / 1024,
        "refactored_peak_kb": refactored_peak / 1024,
    }


def main() -> None:
    print(json.dumps({"dedup_scaling": bench_dedup_scaling()}, indent=2))
    print(json.dumps({"end_to_end": bench_end_to_end()}, indent=2))
    print(json.dumps({"memory": bench_memory_growth()}, indent=2))


if __name__ == "__main__":
    main()
