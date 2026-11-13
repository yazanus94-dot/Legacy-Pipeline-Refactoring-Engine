"""Exception hierarchy for the refactored pipeline."""

from __future__ import annotations

from typing import Any


class PipelineError(Exception):
    """Base class for pipeline errors."""


class RecordError(PipelineError):
    """A single record failed validation; the record id is preserved."""

    def __init__(self, record_id: Any, reason: str) -> None:
        self.record_id = record_id
        self.reason = reason
        super().__init__(f"record {record_id!r}: {reason}")


class ChunkError(PipelineError):
    """Raised for invalid chunking configuration."""


class PipelineConfigError(PipelineError):
    """Raised for invalid concurrency or size configuration."""
