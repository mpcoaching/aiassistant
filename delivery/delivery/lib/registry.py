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


def login(registry: str, username: str, password: str) -> None:
    result = run(["docker", "login", registry, "-u", username, "--password-stdin"], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker login failed: {result.stderr}")


def logout(registry: str) -> None:
    run(["docker", "logout", registry], check=False)


def push(service: str, tag: str) -> None:
    image = f"registry.local.test/aiassistant/{service}:{tag}"
    result = run(["docker", "push", image], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker push failed for {image}: {result.stderr}")


def pull(service: str, tag: str) -> None:
    image = f"registry.local.test/aiassistant/{service}:{tag}"
    result = run(["docker", "pull", image], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker pull failed for {image}: {result.stderr}")


def digest(service: str, tag: str) -> str:
    image = f"registry.local.test/aiassistant/{service}:{tag}"
    result = run(["docker", "inspect", image, "--format", "{{index .RepoDigests 0}}"], check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    return result.stdout.strip().split("@")[-1]
