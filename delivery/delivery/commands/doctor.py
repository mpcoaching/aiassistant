from __future__ import annotations

import socket
import subprocess

import typer
from rich.console import Console

console = Console()


def doctor() -> None:
    checks = [
        ("docker", _check_docker),
        ("gitea", _check_gitea),
        ("registry", _check_registry),
        ("postgres", _check_postgres),
    ]
    all_ok = True
    for name, check in checks:
        ok, msg = check()
        status = "[green]ok[/green]" if ok else "[red]fail[/red]"
        console.print(f"{name}: {status} {msg}")
        if not ok:
            all_ok = False
    if not all_ok:
        raise typer.Exit(1)


def _check_docker() -> tuple[bool, str]:
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        return True, "Docker is available"
    except Exception as exc:
        return False, str(exc)


def _check_gitea() -> tuple[bool, str]:
    try:
        import requests
        resp = requests.get("https://gitea.local.test/api/v1/version", timeout=5, verify=False)
        if resp.status_code == 200:
            return True, f"Gitea {resp.json().get('version', 'unknown')}"
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


def _check_registry() -> tuple[bool, str]:
    try:
        import requests
        resp = requests.get("http://registry.local.test:5000/v2/", timeout=5)
        if resp.status_code == 200 or resp.status_code == 401:
            return True, "Registry reachable"
        return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, str(exc)


def _check_postgres() -> tuple[bool, str]:
    try:
        import requests
        resp = requests.get("http://postgres:5432", timeout=5)
        return True, "Postgres reachable"
    except Exception as exc:
        return False, str(exc)
