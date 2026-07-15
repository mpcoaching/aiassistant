from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def deploy(compose_file: Path, env_file: Optional[Path] = None) -> None:
    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "--remove-orphans"]
    if env_file:
        cmd.extend(["--env-file", str(env_file)])
    result = run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker compose up failed: {result.stderr}")


def rollback(compose_file: Path, env_file: Optional[Path] = None) -> None:
    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "--remove-orphans"]
    if env_file:
        cmd.extend(["--env-file", str(env_file)])
    result = run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker compose rollback failed: {result.stderr}")


def logs(compose_file: Path, service: Optional[str] = None, follow: bool = False) -> str:
    cmd = ["docker", "compose", "-f", str(compose_file), "logs"]
    if service:
        cmd.append(service)
    if follow:
        cmd.append("-f")
    result = run(cmd, check=False)
    if result.returncode != 0:
        return result.stderr
    return result.stdout


def ps(compose_file: Path) -> str:
    result = run(["docker", "compose", "-f", str(compose_file), "ps"], check=False)
    return result.stdout if result.returncode == 0 else result.stderr
