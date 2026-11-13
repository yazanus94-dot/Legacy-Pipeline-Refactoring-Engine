# Before / After

A side-by-side of the two states, defect by defect. Evidence column links
to the test or benchmark that *proves* the delta.

| # | Concern | Legacy (`legacy/pipeline_v1.py`) | Refactored (`src/refactor_engine/`) | Evidence |
|---|---|---|---|---|
| D1 | Duplicate detection | O(N²) pairwise scan; 2.2 s at 8k records | O(N) hash-set single pass; 2.5 ms at 8k (**875x**) | `benchmarks/results.md` §1, `test_refactored_is_linear` |
| D2 | Memory | Module-level `_RECORD_CACHE`, 4.7x growth across runs | Stateless streaming; no globals | `benchmarks/results.md` §3, `test_refactored_keeps_no_global_state` |
| D3 | Function purity | Mutable default arg leaks state across calls | Pure functions, no accumulator args | `test_refactored_pure_function` |
| D4 | Chunking | Boundary records processed twice (601 out for 600 in) | Disjoint chunk generator; property test for exactness | `test_legacy_double_counts_boundary_records` |
| D5 | Money math | Binary float totals drift (~1.4e-12 / 1000 adds) | Integer cents, exact for any volume | `test_cents_aggregation_is_exact` |
| D6 | Errors | Bare `except: continue` silently drops corrupt rows | Typed `RecordError` list on the result | `test_corrupt_rows_are_reported_not_swallowed` |
| D7 | I/O concurrency | Serial sleeps; latency-bound | asyncio pool (bounded 64), order-preserving (**10.3x**) | `benchmarks/results.md` §2, `test_order_preserved_despite_concurrency` |

## What deliberately did NOT change

- **The deduplication key semantics** -- "same account, amount,
  timestamp" is business intent, not a bug; both engines use it.
- **The enrichment latency contract** -- the refactored engine preserves
  per-record latency simulation so benchmarks compare like with like.
- **Public result shape** -- `records_out / duplicates / total`; the
  refactored result adds typed errors but keeps the legacy fields.

## The one-line summary

The legacy pipeline was correct for tiny inputs and quietly wrong at
scale: quadratic dedup, leaking memory, duplicated boundary records,
drifting money totals, and silently swallowed errors. The refactored
engine is linear, stateless, exact, concurrent -- and every claim above
is pinned by a test or a reproducible measurement, not by narrative.
