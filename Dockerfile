FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY legacy/ ./legacy/
COPY tests/ ./tests/
COPY benchmarks/ ./benchmarks/

RUN pip install --no-cache-dir -e .

CMD ["python", "benchmarks/benchmark.py"]
