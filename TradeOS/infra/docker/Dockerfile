# TradeOS Dockerfile
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl git && rm -rf /var/lib/apt/lists/*

RUN pip install uv

FROM base AS builder
WORKDIR /app
COPY pyproject.toml ./
RUN uv pip install --system -e ".[full]"

FROM base AS production
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY core/ ./core/
COPY apps/ ./apps/
COPY infra/ ./infra/
COPY pyproject.toml ./
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
