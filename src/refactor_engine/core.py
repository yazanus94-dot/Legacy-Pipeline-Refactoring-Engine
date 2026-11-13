"""Core aggregates and dataset synthesis for benchmarks and tests."""

from __future__ import annotations

import random
from typing import Any


def synthesize_dataset(
    n: int,
    duplicate_rate: float = 0.02,
    seed: int = 1234,
    missing_amount_every: int = 0,
) -> list[dict[str, Any]]:
    """Deterministic transaction-log synthesis.

    ``duplicate_rate`` of records are exact re-occurrences of earlier rows
    (same account/amount/ts under a new id). ``missing_amount_every`` is 0
    (disabled) or a stride that injects corrupt rows for error-path tests.
    """
    rng = random.Random(seed)
    raw: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for i in range(n):
        if ledger and rng.random() < duplicate_rate:
            src = rng.choice(ledger)
            raw.append(
                {
                    "id": f"tx-{i}",
                    "account": src["account"],
                    "amount": src["amount"],
                    "ts": src["ts"],
                }
            )
        else:
            rec = {
                "id": f"tx-{i}",
                "account": f"acct-{rng.randint(1, 50):03d}",
                "amount": round(rng.uniform(-5000.0, 5000.0), 2),
                "ts": f"2026-01-{rng.randint(1, 28):02d}T{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00Z",
            }
            raw.append(rec)
            ledger.append(rec)
    if missing_amount_every > 0:
        for i in range(missing_amount_every - 1, n, missing_amount_every):
            raw[i] = {"id": raw[i]["id"], "account": "corrupt", "ts": "bad"}
    return raw
