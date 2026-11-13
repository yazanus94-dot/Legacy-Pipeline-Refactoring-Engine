# Design Decisions

## 1. Integer cents instead of Decimal for money

**Decision:** convert to integer cents at parse time; keep floats only at
the raw-input boundary.

**Trade-off:**

| Option | Exactness | Speed | Serialization |
|---|---|---|---|
| Binary float (legacy) | drifts | fastest | lossy pennies |
| `Decimal` everywhere | exact | ~3-8x slower per op | clean |
| **Integer cents (chosen)** | exact | near-float speed | trivial JSON int |

`Decimal` was the runner-up; the benchmark showed cents arithmetic is
materially faster in hot aggregation loops, and cents *are* the
accounting unit of the business domain.

## 2. asyncio over threading/multiprocessing for enrichment

**Decision:** bounded asyncio pool (`Semaphore`) rather than threads or
processes.

- The enrichment stage is **I/O-bound** (network in production, sleep in
  the simulation): asyncio schedules thousands of cheap coroutines with
  no GIL contention on the wait path.
- Threads add context-switch and GIL overhead without helping I/O waits;
  processes are disqualified by serialization cost of per-record data.
- A **bounded** pool is deliberate: unbounded task creation for 100k
  records would spike memory; the semaphore keeps the working set flat.
- Output order is restored deterministically by awaiting tasks in input
  order -- concurrency with reproducible results.

## 3. Streaming parse with error callback

**Decision:** `parse_records(raw, on_error=...)` yields valid records and
reports failures via callback instead of raising.

**Reasoning:** a raising generator dies on its first bad record -- the
pipeline would lose everything after row 40,000 because of one corrupt
row. Lenient-by-default with *explicit, typed reporting* preserves the
audit trail the legacy `except: continue` destroyed, without the
all-or-nothing strictness of exceptions.

## 4. Keep the legacy module untouched

**Decision:** `legacy/pipeline_v1.py` is frozen; fixes live only in
`src/refactor_engine/`.

**Reasoning:** the "before" state is evidence. Rewriting it in place
would destroy the ability to benchmark, to re-run defect repro tests,
and to demonstrate the delta. The repro tests import the frozen module
and prove each documented defect still reproduces.

## 5. Determinism despite concurrency

**Decision:** concurrent execution, deterministic output -- enrich tasks
are awaited in input order.

**Reasoning:** a pipeline whose results depend on scheduler timing is
untestable. Every property test can therefore assert exact output
equality, and benchmarks compare identical logical work.

## 6. tracinemalloc for the leak claim

**Decision:** use stdlib `tracemalloc`, not `memory_profiler`, for
memory evidence.

**Reasoning:** `tracemalloc` measures allocation *attribution* (peak
traced memory per code path) with zero dependencies and reproducible
numbers; profiler-based "before/after" memory screenshots are noisy and
hard to reproduce. The benchmark also runs the leak scenario both ways
(cache cleared vs not) so the delta isolates the defect.
