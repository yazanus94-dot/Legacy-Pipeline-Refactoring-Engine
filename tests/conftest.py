"""Shared fixtures."""

from __future__ import annotations

import pytest

from refactor_engine import synthesize_dataset


@pytest.fixture(scope="session")
def clean_dataset():
    return synthesize_dataset(200, duplicate_rate=0.05, seed=42)


@pytest.fixture(scope="session")
def corrupt_dataset():
    return synthesize_dataset(200, duplicate_rate=0.05, seed=42, missing_amount_every=20)
