# Multi-stage build for kfc-event-consumer (Server_Design.md §4).
# Build context is the repo root (see deploy/docker-compose.yml `build.context`).

FROM python:3.12-slim AS builder
WORKDIR /build
COPY certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates
COPY requirements-server.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements-server.txt

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser
COPY --from=builder /venv /venv
WORKDIR /app
COPY chess_engine ./chess_engine
COPY server ./server
COPY services/kfc-event-consumer/src ./services/kfc-event-consumer/src

ENV PATH="/venv/bin:${PATH}" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED="1" \
    METRICS_PORT="9090"

USER appuser
EXPOSE 9090

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9090/healthz', timeout=2).status == 200 else 1)"

CMD ["python", "/app/services/kfc-event-consumer/src/main.py"]
