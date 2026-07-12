FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      gnupg \
      git \
      gh \
      python3 \
      python3-pip \
      python3-venv \
      docker.io \
      docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN npm --version && node --version && python3 --version && pip3 --version

RUN pip3 install --no-cache-dir pytest pytest-cov
