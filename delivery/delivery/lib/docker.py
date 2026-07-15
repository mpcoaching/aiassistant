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


def buildx_build(
    service: str,
    tag: str,
    context: Path,
    dockerfile: Path,
    platforms: list[str] | None = None,
    push: bool = False,
) -> str:
    cmd = [
        "docker", "buildx", "build",
        "--builder", "default",
        "-t", f"registry.local.test/aiassistant/{service}:{tag}",
        "-f", str(dockerfile),
        str(context),
    ]
    if platforms:
        cmd.extend(["--platform", ",".join(platforms)])
    if push:
        cmd.append("--push")
    else:
        cmd.extend(["--load", "--output", "type=docker"])
    result = run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"docker buildx failed for {service}: {result.stderr}")
    return tag


def buildx_build_parallel(
    services: list[tuple[str, Path, Path]],
    tag: str,
    platforms: list[str] | None = None,
    push: bool = False,
) -> dict[str, str]:
    results = {}
    for service, context, dockerfile in services:
        try:
            results[service] = buildx_build(service, tag, context, dockerfile, platforms, push)
        except Exception as exc:
            results[service] = f"ERROR: {exc}"
    return results
