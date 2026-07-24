FROM gitea/runner-images:ubuntu-latest

USER root

ENV DEBIAN_FRONTEND=noninteractive

# Basic utilities
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"

# Verify tools
RUN python --version \
    && pip --version \
    && uv --version \
    && git --version \
    && jq --version \
    && yq --version

WORKDIR /workspace