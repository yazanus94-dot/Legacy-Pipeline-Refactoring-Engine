#!/usr/bin/env bash
set -euo pipefail
pytest -v --cov=refactor_engine --cov-report=term-missing
echo "--- Benchmark ---"
python benchmarks/benchmark.py
