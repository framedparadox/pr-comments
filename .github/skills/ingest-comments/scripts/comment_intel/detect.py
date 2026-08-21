"""Git repository and hosting-platform detection."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Runner = Callable[[list[str], Path | None], subprocess.CompletedProcess]


@dataclass
class RepoIdentity:
    git_root: Path
    provider: str
    host: str
    owner: str
    repo: str
    remote_url: str | None
    base_branch: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


class DetectionError(SystemExit):
    """Raised/used when the user must disambiguate."""


def default_runner(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, env=env)


def git_root(start: str | Path | None = None, runner: Runner = default_runner) -> Path:
    cwd = Path(start or ".").resolve()
    result = runner(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], cwd)
    if result.returncode != 0:
        raise SystemExit(f"not a git repository: {cwd}\n{result.stderr.strip()}")
    return Path(result.stdout.strip()).resolve()


def _git(runner: Runner, root: Path, *args: str) -> str:
    result = runner(["git", "-C", str(root), *args], root)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


_SSH_SCP = re.compile(r"^git@([^:]+):(.+)$")
_SSH_SCHEME = re.compile(r"^ssh://(?:git@)?([^/]+)/(.+)$")
_HTTPS = re.compile(r"^https?://([^/]+)/(.+)$")


def parse_remote_url(url: str) -> tuple[str, str, str, str]:
    """Return (provider, host, owner, repo) from a git remote URL."""
    raw = url.strip()
    if raw.endswith(".git"):
        raw = raw[:-4]
    host = ""
    path = ""
    match = _SSH_SCP.match(raw)
    if match:
        host, path = match.group(1), match.group(2)
    else:
        match = _SSH_SCHEME.match(raw)
        if match:
            host, path = match.group(1), match.group(2)
        else:
            match = _HTTPS.match(raw)
            if match:
                host, path = match.group(1), match.group(2)
            else:
                raise SystemExit(f"unrecognized remote URL: {url}")
    host = host.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if ":" in host and host.count(":") == 1 and not host.replace(":", "").isdigit():
        # user@host already handled; drop unexpected scheme leftovers
        pass
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise SystemExit(f"cannot parse owner/repo from remote URL: {url}")
    repo = parts[-1]
    owner = "/".join(parts[:-1])
    return provider_from_host(host), host, owner, repo


def provider_from_host(host: str) -> str:
    host = host.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if host == "github.com" or host.startswith("github.") or host.endswith(".github.com") or host == "github":
        return "github"
    if host == "gitlab.com" or host.startswith("gitlab.") or "gitlab" in host:
        return "gitlab"
    if host == "bitbucket.org" or "bitbucket" in host:
        return "bitbucket"
    if host in {"codeberg.org", "gitea.com"} or "gitea" in host or "forgejo" in host:
        return "gitea"
    return "unknown"


def detect_identity(
    git_dir: str | Path | None = None,
    remote: str = "origin",
    runner: Runner = default_runner,
) -> RepoIdentity:
    root = git_root(git_dir, runner=runner)
    url = _git(runner, root, "remote", "get-url", remote)
    if not url:
        url = _git(runner, root, "config", "--get", f"remote.{remote}.url")
    if not url:
        return RepoIdentity(
            git_root=root,
            provider="unknown",
            host="local",
            owner="local",
            repo=root.name,
            remote_url=None,
        )
    provider, host, owner, repo = parse_remote_url(url)
    return RepoIdentity(
        git_root=root,
        provider=provider,
        host=host,
        owner=owner,
        repo=repo,
        remote_url=url,
    )


def branch_exists(root: Path, name: str, runner: Runner = default_runner) -> bool:
    for ref in (f"refs/heads/{name}", f"refs/remotes/origin/{name}"):
        result = runner(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", ref], root)
        if result.returncode == 0:
            return True
    return False


def origin_head_branch(root: Path, runner: Runner = default_runner) -> str | None:
    symbolic = _git(runner, root, "symbolic-ref", "refs/remotes/origin/HEAD")
    if symbolic.startswith("refs/remotes/origin/"):
        return symbolic.split("/")[-1]
    return None


def resolve_base_branch(
    identity: RepoIdentity,
    requested: str | None = None,
    runner: Runner = default_runner,
    api_default: str | None = None,
) -> str:
    if requested:
        return requested
    if api_default:
        return api_default
    head = origin_head_branch(identity.git_root, runner=runner)
    if head:
        return head
    present = [name for name in ("main", "master") if branch_exists(identity.git_root, name, runner=runner)]
    if len(present) == 1:
        return present[0]
    if "main" in present:
        return "main"
    if "master" in present:
        return "master"
    raise SystemExit(
        "base branch is ambiguous. Pass --base-branch (tried origin/HEAD, then main, then master)."
    )
