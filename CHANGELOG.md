# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] - 2026-11-12

### Added
- Refactored engine: streaming validation with typed `RecordError`
  reporting, O(N) hash-based deduplication, exact integer-cent
  aggregation, disjoint chunk generator, and bounded-concurrency
  asyncio enrichment with deterministic output order.
- Frozen legacy "before" state (`legacy/pipeline_v1.py`) with six
  documented defects, each pinned by a reproduction test.
- Reproducible before/after benchmark: 875x dedup speedup at 8k
  records, 10.3x end-to-end speedup, tracemalloc leak evidence.
- Hypothesis property suite: brute-force dedup oracle, Decimal
  aggregation reference, chunking exactness, concurrency order, parser
  fuzzing (caught a real `OverflowError` bug in the fix).
- Docker Compose services (demo / tests / benchmark) and CI pipeline.
