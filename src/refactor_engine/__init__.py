"""refactor_engine: high-performance, correct replacement for the legacy pipeline."""

from __future__ import annotations

from refactor_engine.algorithms import (
    aggregate_cents,
    find_duplicates,
    risk_score,
)
from refactor_engine.core import synthesize_dataset
from refactor_engine.exceptions import (
    ChunkError,
    PipelineConfigError,
    PipelineError,
    RecordError,
)
from refactor_engine.services import (
    PipelineResult,
    chunks,
    enrich_all,
    enrich_stream,
    parse_records,
    run_pipeline,
)

__version__ = "2.0.0"

__all__ = [
    "PipelineResult",
    "synthesize_dataset",
    "PipelineError",
    "RecordError",
    "ChunkError",
    "PipelineConfigError",
    "parse_records",
    "find_duplicates",
    "enrich_stream",
    "enrich_all",
    "chunks",
    "aggregate_cents",
    "risk_score",
    "run_pipeline",
]
