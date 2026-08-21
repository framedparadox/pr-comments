"""Adapter registry and shared PR metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..detect import RepoIdentity
from ..proc import Runner, default_runner


@dataclass
class PullRequest:
    number: int
    title: str
    state: str
    url: str | None
    created_at: str | None
    updated_at: str | None
    merged_at: str | None = None
    author: str | None = None


@dataclass
class IngestRequest:
    identity: RepoIdentity
    base_branch: str
    cutoff: str | None = None
    runner: Runner = default_runner
    http_get: Callable[..., Any] | None = None
    local_json: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Adapter:
    name = "base"

    def fetch(self, request: IngestRequest) -> list[dict[str, Any]]:
        raise NotImplementedError

    def default_branch(self, request: IngestRequest) -> str | None:
        return None


ADAPTERS: dict[str, Adapter] = {}


def register(adapter: Adapter) -> Adapter:
    ADAPTERS[adapter.name] = adapter
    return adapter


def get_adapter(name: str) -> Adapter:
    if name not in ADAPTERS:
        raise SystemExit(
            f"unsupported host provider '{name}'. "
            "Pass --host github|gitlab|bitbucket|gitea or --local-json."
        )
    return ADAPTERS[name]


def _load_adapters() -> None:
    from . import bitbucket, gitea, github, gitlab, local_json  # noqa: F401


_load_adapters()
