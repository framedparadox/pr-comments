"""Subprocess and HTTP helpers shared by adapters."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

Runner = Callable[[list[str], Path | None], subprocess.CompletedProcess]


def default_runner(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, env=env)


def which(name: str) -> str | None:
    return shutil.which(name)


def parse_cli_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = text.replace("][", ",")
        return json.loads(repaired)


def run_json(runner: Runner, args: list[str], cwd: Path | None = None) -> Any:
    result = runner(args, cwd)
    if result.returncode != 0:
        raise SystemExit(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stderr.strip()}"
        )
    return parse_cli_json(result.stdout)


def http_get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 60) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            link = resp.headers.get("Link") or resp.headers.get("link")
            data = json.loads(body) if body else None
            return data, link
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} for {url}: {detail[:500]}") from exc


def parse_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            start = part.find("<")
            end = part.find(">")
            if start >= 0 and end > start:
                return part[start + 1 : end]
    return None


def env_token(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None
