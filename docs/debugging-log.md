# Debugging Log

Root-cause analysis of every documented defect in the legacy pipeline, in
the order they were identified during the reverse-engineering review.
Each defect has a repro test: `tests/unit/test_legacy_defects.py`.

## D1 -- O(N²) duplicate detection

- **Symptom:** throughput collapsed as the transaction log grew; 8k
  records took 2.2 s *only* for dedup (measured).
- **Root cause:** `flag_duplicates` compares every record against every
  later record (`for i: for j > i`), i.e., ~N²/2 comparisons.
- **Debugging approach:** timed the function at N = 1k/2k/4k/8k and
  observed exact 4x growth per doubling -- the signature of quadratic
  complexity, not a constant slowdown.
- **Fix:** single pass with a hashable dedup key
  (`account, amount_cents, ts`) into a set -- O(N) time, O(N) memory.
- **Regression tests:** `test_legacy_duplicate_flags_are_correct_but_slow`,
  `test_refactored_is_linear` (scaling bound), and the Hypothesis oracle
  test proving the O(N) version agrees with brute-force pairwise output.

## D2 -- Unbounded module-level cache

- **Symptom:** long-lived worker processes grew monotonically in memory.
- **Root cause:** `parse_records` appended every parsed record to
  `_RECORD_CACHE`, a module-level list never cleared -- every record from
  every run stays alive for the process lifetime.
- **Evidence:** tracemalloc over 5 runs: 98 KB with cache cleared between
  runs vs 458.9 KB without (4.7x) -- see `benchmarks/results.md` §3.
- **Fix:** stream parsing (generator), no module-level state; a lint-style
  regression test forbids `_RECORD*` globals from returning.
- **Regression test:** `test_refactored_keeps_no_global_state`.

## D3 -- Mutable default argument

- **Symptom:** duplicate lists accumulated results *across calls*; a
  caller reusing the returned list as the `dupes` parameter saw flags
  from previous datasets.
- **Root cause:** `flag_duplicates(records, dupes=None)` mutates the
  caller-supplied list; combined with the common idiom
  `dupes = flag_duplicates(recs, dupes)` this cross-contaminates calls.
- **Fix:** pure functions only -- the refactored `find_duplicates`
  allocates its own output and takes no accumulator argument.
- **Regression test:** `test_refactored_pure_function`.

## D4 -- Chunk boundary double-counting

- **Symptom:** totals and record counts were consistently slightly too
  high, scaled with `len(records) // chunk_size`, and no record was ever
  reported as an error.
- **Root cause:** `records[start : start + size + 1]` grabs one record
  beyond the chunk, and the next chunk starts on that same record again:
  each chunk boundary processes one record twice.
- **Evidence:** for a 600-record input with chunk size 512 the legacy
  pipeline emits 601 enriched records (proven in
  `tests/integration/test_before_after.py`).
- **Fix:** explicit disjoint chunk generator with a property test that
  every record appears exactly once for arbitrary sizes.
- **Regression tests:** `test_legacy_double_counts_boundary_records`,
  `test_chunking_preserves_every_record_exactly_once` (property).

## D5 -- Float accumulation drift

- **Symptom:** reported totals were pennies off the ledger sum on large
  batches -- never by much, but always in some direction.
- **Root cause:** running totals in binary floating point; 1000 adds of
  0.1 drift by ~1.4e-12 (measured), growing with addend count.
- **Fix:** money stored as integer cents end-to-end; aggregation is exact
  for any realistic volume.
- **Regression tests:** `test_legacy_total_drifts`,
  `test_cents_aggregation_is_exact` (Decimal-reference property test).

## D6 -- Silent exception swallowing

- **Symptom:** corrupt rows disappeared from reports with no signal;
  totals quietly covered only "surviving" records.
- **Root cause:** bare `except Exception: continue` inside the
  aggregation loop.
- **Fix:** validation happens at parse time; failures are collected into
  a typed `RecordError` list on the result object, and valid records
  still flow through (`test_corrupt_rows_are_reported_not_swallowed`).
- **Bonus catch:** the Hypothesis fuzz of the *refactored* parser found
  an `OverflowError` on extreme floats that the original `except`
  tuple missed -- fixed by adding `OverflowError` to the handled set.
  Property-based testing caught a bug in the fix itself.

## D7 -- Serial I/O enrichment (performance defect)

- **Symptom:** pipeline time grew linearly with record count even though
  the CPU work per record was negligible.
- **Root cause:** per-record synchronous I/O (simulated 0.5 ms); the
  process was latency-bound, not CPU-bound.
- **Fix:** bounded-concurrency asyncio pool (`Semaphore(64)`) with
  deterministic input-order output. Measured 10.3x end-to-end.
- **Regression test:** `test_order_preserved_despite_concurrency`,
  `test_concurrency_parameter_accepted`.
