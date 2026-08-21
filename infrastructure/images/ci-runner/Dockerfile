FROM gitea/runner-images:ubuntu-latest

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    nodejs \
    npm \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*


# Install Mike Farah yq
RUN curl -L \
    https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
    -o /usr/local/bin/yq \
    && chmod +x /usr/local/bin/yq


# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:${PATH}"


# Remove Debian's externally-managed restriction so pip can install packages
RUN rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED

# Install common Python tools
RUN pip install --no-cache-dir --break-system-packages uv pytest pytest-cov ruff pyyaml


# Verify tools
RUN python --version \
    && pip --version \
    && uv --version \
    && git --version \
    && jq --version \
    && yq --version \
    && node --version \
    && npm --version \
    && ruff --version \
    && pytest --version# ci-runner trigger Fri Aug 21 11:41:54 AM AEST 2026
