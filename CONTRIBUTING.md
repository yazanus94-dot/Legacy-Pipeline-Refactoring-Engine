# Contributing to Legacy-Pipeline-Refactoring-Engine

Thank you for considering a contribution. This project's core promise is
that every performance or correctness claim is pinned by a test or a
reproducible measurement.

## Ground rules

1. **The legacy module is frozen.** Never "improve" `legacy/pipeline_v1.py`;
   it is the benchmark and defect-repro baseline. Fixes belong in
   `src/refactor_engine/`.
2. **Bugs must be reproducible.** New fixes require: a failing repro test
   first, the fix second, and a debugging-log entry explaining root cause.
3. **Money stays in integer cents.** No float arithmetic in the money path.
4. **Concurrency stays bounded.** Any new concurrent stage must use an
   explicit bound and preserve deterministic output order.
5. **Type hints everywhere.** `mypy --strict` must pass.

## Workflow

```bash
git clone https://github.com/<you>/Legacy-Pipeline-Refactoring-Engine
cd Legacy-Pipeline-Refactoring-Engine
pip install -r requirements.txt
pip install -e .
ruff check .
mypy src
pytest -v
python benchmarks/benchmark.py
```

## Commit style

Small, meaningful commits referencing the defect IDs:
`fix(D4): disjoint chunk generator eliminates boundary double-count`,
`bench: re-measure dedup scaling after O(N) fix`.

## Pull requests

- Reference the defect ID or issue.
- Include before/after benchmark numbers for performance changes.
- All CI checks must be green.
