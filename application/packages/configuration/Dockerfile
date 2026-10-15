FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY local.test.crt /usr/local/share/ca-certificates/local.test.crt
COPY rootCA.pem /usr/local/share/ca-certificates/rootCA.crt
RUN update-ca-certificates

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src/ /app/src/

RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir -e . 2>/dev/null || true

COPY configs/sources.yaml /etc/platform/sources.yaml
COPY configs/config.json /etc/platform/config.json

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "configuration.server"]