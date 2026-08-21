"""End-to-end extract: fetch comments, write CSV/JSON, build dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dashboard import build_payload, utc_now, write_dashboard
from .detect import (
    RepoIdentity,
    detect_identity,
    parse_repo_slug,
    provider_from_host,
    resolve_base_branch,
)
from .export import read_json, write_csv, write_json, write_jsonl
from .github import GitHubExtractor
from .paths import default_output_dir
from .proc import Runner, default_runner
from .schema import CSV_FIELDS, JSON_EXTRA_FIELDS


def resolve_identity(
    git_dir: str | Path | None,
    host: str | None,
    repo: str | None,
    base_branch: str | None,
    runner: Runner = default_runner,
) -> RepoIdentity:
    identity: RepoIdentity | None = None
    if git_dir or not repo:
        try:
            identity = detect_identity(git_dir, runner=runner)
        except SystemExit:
            if not repo:
                raise
            identity = None
    if repo:
        hostname = host or (identity.host if identity and identity.host != "local" else "github.com")
        if hostname in {"github", "gitlab"}:
            hostname = "github.com" if hostname == "github" else "gitlab.com"
        provider, parsed_host, owner, name = parse_repo_slug(repo, host=hostname)
        identity = RepoIdentity(
            git_root=identity.git_root if identity else None,
            provider=provider,
            host=parsed_host,
            owner=owner,
            repo=name,
            remote_url=identity.remote_url if identity else None,
        )
    if identity is None:
        raise SystemExit("pass --repo owner/name or run inside a git checkout")
    if host:
        if host in {"github", "gitlab"}:
            identity.provider = host
            if host == "github" and identity.host in {"local", ""}:
                identity.host = "github.com"
        else:
            identity.host = host
            identity.provider = provider_from_host(host)
    return identity


def extract(
    *,
    git_dir: str | Path | None = None,
    host: str | None = None,
    repo: str | None = None,
    base_branch: str | None = None,
    output_dir: str | Path | None = None,
    since: str | None = None,
    max_prs: int | None = None,
    runner: Runner = default_runner,
    transport=None,
    local_json: str | Path | None = None,
) -> dict[str, Any]:
    identity = resolve_identity(git_dir, host, repo, base_branch, runner=runner)
    if identity.provider not in {"github", "unknown"} and not local_json:
        raise SystemExit(
            f"provider '{identity.provider}' is not supported yet. This extractor fetches GitHub pull requests."
        )
    extractor = GitHubExtractor(
        identity.host if identity.host != "local" else "github.com",
        identity.slug,
        runner=runner,
        cwd=identity.git_root,
        transport=transport,
    )
    api_default = None
    if not local_json:
        try:
            api_default = extractor.default_branch()
        except SystemExit:
            api_default = None
    identity.base_branch = resolve_base_branch(
        identity,
        requested=base_branch,
        runner=runner,
        api_default=api_default,
    )
    start = Path(output_dir) if output_dir else Path(git_dir or identity.git_root or ".")
    artifacts = (
        Path(output_dir).resolve()
        if output_dir
        else default_output_dir(start, identity.host, identity.owner, identity.repo)
    )
    artifacts.mkdir(parents=True, exist_ok=True)

    if local_json:
        comments = _load_local(Path(local_json), identity)
        pr_count = len({c.get("pr_number") for c in comments})
    else:
        prs = extractor.list_pull_requests(identity.base_branch or "main")
        if max_prs is not None:
            prs = prs[: max(0, max_prs)]
        comments = extractor.fetch_comments(prs)
        pr_count = len(prs)

    if since:
        comments = [row for row in comments if (row.get("comment_date") or "") >= since]

    extracted_at = utc_now()
    payload = build_payload(
        host=identity.host,
        repo=identity.slug,
        base_branch=identity.base_branch or "main",
        comments=comments,
        extracted_at=extracted_at,
        pull_request_count=pr_count,
    )
    write_csv(artifacts / "comments.csv", comments)
    write_json(artifacts / "comments.json", comments)
    write_jsonl(artifacts / "comments.jsonl", comments)
    write_dashboard(artifacts / "dashboard.html", payload)
    meta = {
        "repo": identity.slug,
        "host": identity.host,
        "base_branch": identity.base_branch,
        "extracted_at": extracted_at,
        "pull_request_count": pr_count,
        "comment_count": len(comments),
        "csv_fields": list(CSV_FIELDS),
        "json_extra_fields": list(JSON_EXTRA_FIELDS),
        "output_dir": str(artifacts),
    }
    write_json(artifacts / "meta.json", meta)
    return {
        "identity": {
            "provider": identity.provider,
            "host": identity.host,
            "repo": identity.slug,
            "base_branch": identity.base_branch,
        },
        "output_dir": str(artifacts),
        "csv": str(artifacts / "comments.csv"),
        "json": str(artifacts / "comments.json"),
        "dashboard": str(artifacts / "dashboard.html"),
        "pull_request_count": pr_count,
        "comment_count": len(comments),
        "stats": payload["stats"],
    }


def _load_local(path: Path, identity: RepoIdentity) -> list[dict[str, Any]]:
    data = read_json(path, default=None)
    if data is None:
        raise SystemExit(f"could not read {path}")
    if isinstance(data, dict) and "comments" in data:
        data = data["comments"]
    if not isinstance(data, list):
        raise SystemExit("--local-json must be a JSON array of comment rows")
    for row in data:
        row.setdefault("repo", identity.slug)
        row.setdefault("host", identity.host)
        row.setdefault("provider", "github")
    return data
