# Multi-stage build for kfc-migrations (Server_Design.md §5/§9 Phase 2).
# A one-off runner, not a long-running service: applies Alembic migrations
# plus Citus create_distributed_table DDL, then exits 0.
# Build context is the repo root (see deploy/docker-compose.yml
# `build.context`), solely so this image can also trust certs/ like every
# other service — otherwise it has no dependency on the rest of the repo.

FROM python:3.12-slim AS builder
WORKDIR /build
COPY certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates
COPY services/kfc-migrations/requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser
COPY --from=builder /venv /venv
WORKDIR /app
COPY services/kfc-migrations/alembic.ini .
COPY services/kfc-migrations/migrations ./migrations
COPY services/kfc-migrations/wait_for_postgres.py .
COPY services/kfc-migrations/entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV PATH="/venv/bin:${PATH}" \
    PYTHONUNBUFFERED="1"

USER appuser

ENTRYPOINT ["./entrypoint.sh"]
