FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY packages/workflow_runner/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY packages/configuration /packages/configuration
COPY packages/ai /packages/ai
COPY packages/bus /packages/bus
COPY packages/langgraph /packages/langgraph
COPY packages/capability_registry /packages/capability_registry

COPY packages/workflow_runner/. /app/

RUN printf '%s\n' '#!/usr/bin/env python3' \
    '"""Startup wait-loop helper."""' \
    'import socket' \
    'import subprocess' \
    'import sys' \
    'import time' \
    '' \
    'def wait(host, port):' \
    '    for _ in range(150):' \
    '        try:' \
    '            with socket.create_connection((host, port), 2):' \
    '                return' \
    '        except OSError:' \
    '            time.sleep(2)' \
    '    sys.exit(1)' \
    '' \
    'def main():' \
    '    args = sys.argv[1:]' \
    '    if "--" in args:' \
    '        idx = args.index("--")' \
    '        hosts, rest = args[:idx], args[idx + 1:]' \
    '    else:' \
    '        hosts, rest = args, []' \
    '    for spec in hosts:' \
    '        host, _, port = spec.rpartition(":")' \
    '        wait(host, int(port))' \
    '    if rest:' \
    '        sys.exit(subprocess.run(rest).returncode)' \
    '' \
    'if __name__ == "__main__":' \
    '    main()' > /wait_for.py && chmod +x /wait_for.py

ENV PYTHONPATH=/app:/packages/configuration/src:/packages/ai/src:/packages/bus/src:/packages/langgraph/src:/packages/capability_registry/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
