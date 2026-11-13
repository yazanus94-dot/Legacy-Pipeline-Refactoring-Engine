# Security Considerations

This project processes synthetic transaction data, but the pipeline
pattern is production-shaped; these are the boundaries that matter.

## Input validation boundary

- Every row passes strict parse-time validation: required fields,
  numeric amounts, bounded conversion to integer cents.
- `OverflowError`, `TypeError`, `ValueError`, `KeyError` are handled
  explicitly (a Hypothesis fuzz test found the `OverflowError` gap -- now
  pinned by `test_parse_never_crashes_and_reports_or_yields`).
- Validation failure is *reported*, never silent: corrupt data cannot
  influence totals without leaving a typed trace.

## Injection surface

- All dataset synthesis is deterministic and internal (`random.Random`
  with fixed seeds); no filesystem, network, or shell input is involved
  in any code path, test, or benchmark.
- The enrichment stage simulates I/O with `asyncio.sleep`; it performs
  no real network calls, so the test suite and benchmarks are hermetic
  and cannot exfiltrate anything.

## Resource bounds

- Enrichment concurrency is bounded by an explicit `Semaphore(64)` --
  an unbounded task fan-out for large batches would be a memory DoS on
  the process itself; the bound keeps peak memory flat regardless of
  input size.
- Aggregation uses integer arithmetic; there is no floating-point
  overflow or NaN path in the money pipeline.

## Error-handling policy

- Errors carry the record id (`RecordError.record_id`) for auditability.
- No bare `except` exists in the refactored engine (the legacy bare
  except was defect D6); `ruff` lint config (`B` rules) enforces this.

## Known limitations

- The simulated I/O layer is intentionally not a real HTTP client; a
  production wiring must add timeouts, retries with jitter, and TLS
  verification -- out of scope for the deterministic benchmark.
- `run_pipeline` materializes the enriched batch; a true streaming
  aggregation for inputs larger than memory is future work (noted in
  the README roadmap).
