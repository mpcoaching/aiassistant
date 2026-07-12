#!/usr/bin/env python3
"""Startup wait-loop helper for the agentic stack.

Used as a container entrypoint to block until upstream dependencies (declared on
the external `ai_net`) accept TCP connections, then exec the real command. This
replaces cross-project `depends_on` (unsupported by Compose across projects).

Usage (as entrypoint):
    python3 /wait_for.py host:port [host:port ...] -- real command args

Example:
    entrypoint: ["python3","/wait_for.py","postgres:5432","redis-agents:6379","--",
                 "litellm","--config","/app/config/config.yaml","--port","4000"]
"""
import socket
import subprocess
import sys
import time


def wait(host: str, port: int) -> None:
    print(f"[wait_for] waiting for {host}:{port}", flush=True)
    for _ in range(150):  # ~5 min at 2s intervals
        try:
            with socket.create_connection((host, port), 2):
                print(f"[wait_for] {host}:{port} is up", flush=True)
                return
        except OSError:
            time.sleep(2)
    print(f"[wait_for] timeout waiting for {host}:{port}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    args = sys.argv[1:]
    if "--" in args:
        idx = args.index("--")
        hosts, rest = args[:idx], args[idx + 1:]
    else:
        hosts, rest = args, []

    for spec in hosts:
        host, _, port = spec.rpartition(":")
        if not host or not port.isdigit():
            print(f"[wait_for] invalid host:port '{spec}'", file=sys.stderr)
            sys.exit(2)
        wait(host, int(port))

    if rest:
        sys.exit(subprocess.run(rest).returncode)


if __name__ == "__main__":
    main()
