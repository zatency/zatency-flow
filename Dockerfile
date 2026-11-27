FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.11-slim
RUN useradd --create-home --shell /bin/bash zatency
WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY src ./src
USER zatency
EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/health')" || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8082"]
