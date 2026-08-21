"""End-to-end ingest → refine → generate → checkpoint → mirror."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapters import IngestRequest, get_adapter
from .checkpoint import default_checkpoint, load_cutoff, read_checkpoint, write_checkpoint
from .detect import RepoIdentity, detect_identity, resolve_base_branch
from .generate import update_derived_skills
from .mirror import mirror_skills
from .paths import artifact_dir
from .refine import merge_uniques
from .report import render_report
from .store import append_jsonl, existing_ids, read_json, read_jsonl, write_json
from .timeutil import max_iso, now_iso


def resolve_identity(
    git_dir: str | Path | None,
    host: str | None,
    repo: str | None,
    base_branch: str | None,
    local_json: str | Path | None,
    runner=None,
) -> RepoIdentity:
    from .detect import default_runner, provider_from_host

    run = runner or default_runner
    identity = detect_identity(git_dir, runner=run)
    known_providers = {"github", "gitlab", "bitbucket", "gitea", "local"}
    if host:
        identity.provider = host if host in known_providers else provider_from_host(host)
        if "." in host or host not in known_providers:
            identity.host = host
    if repo and "/" in repo:
        owner, name = repo.rsplit("/", 1)
        identity.owner, identity.repo = owner, name
    if local_json and identity.provider == "unknown":
        identity.provider = "local"
    api_default = None
    if identity.provider not in {"unknown", "local"}:
        try:
            adapter = get_adapter(identity.provider)
            req = IngestRequest(identity=identity, base_branch=base_branch or "main", runner=run)
            api_default = adapter.default_branch(req)
        except Exception:
            api_default = None
    identity.base_branch = resolve_base_branch(
        identity,
        requested=base_branch,
        runner=run,
        api_default=api_default,
    )
    return identity


def ingest(
    identity: RepoIdentity,
    *,
    cutoff: str | None = None,
    local_json: str | Path | None = None,
    runner=None,
) -> dict[str, Any]:
    artifacts = artifact_dir(identity.git_root, identity.host, identity.owner, identity.repo)
    artifacts.mkdir(parents=True, exist_ok=True)
    cutoff = cutoff if cutoff is not None else load_cutoff(artifacts)
    provider = identity.provider
    if local_json:
        provider = "local"
    if provider == "unknown":
        raise SystemExit(
            "could not detect hosting provider from git remotes. "
            "Pass --host github|gitlab|bitbucket|gitea or --local-json PATH."
        )
    adapter = get_adapter(provider)
    request_kwargs: dict[str, Any] = {
        "identity": identity,
        "base_branch": identity.base_branch or "main",
        "cutoff": cutoff,
        "local_json": Path(local_json) if local_json else None,
    }
    if runner is not None:
        request_kwargs["runner"] = runner
    request = IngestRequest(**request_kwargs)
    fetched = adapter.fetch(request)
    known = existing_ids(artifacts / "comments.jsonl")
    new_records = [r for r in fetched if r.get("id") not in known]
    if new_records:
        append_jsonl(artifacts / "comments.jsonl", new_records)
    all_comments = read_jsonl(artifacts / "comments.jsonl")
    write_json(artifacts / "comments.json", all_comments)
    write_json(artifacts / "ingest_run.json", {"cutoff_used": cutoff, "new": new_records})
    return {
        "artifact_dir": artifacts,
        "new_records": new_records,
        "all_comments": all_comments,
        "cutoff_used": cutoff,
    }


def refine(identity: RepoIdentity) -> dict[str, Any]:
    artifacts = artifact_dir(identity.git_root, identity.host, identity.owner, identity.repo)
    comments = read_jsonl(artifacts / "comments.jsonl")
    existing = read_json(artifacts / "unique.json", default=[]) or []
    existing_keys = {item.get("dedup_key") for item in existing if item.get("dedup_key")}
    uniques, changed = merge_uniques(existing, comments)
    write_json(artifacts / "unique.json", uniques)
    write_json(artifacts / "comments.json", comments)
    last_pr = None
    numbers = [int(c["pr_number"]) for c in comments if c.get("pr_number") is not None]
    if numbers:
        last_pr = max(numbers)
    cutoff = max_iso([c.get("created_at") for c in comments]) or now_iso()
    previous = (artifacts / "REPORT.md").read_text(encoding="utf-8") if (artifacts / "REPORT.md").is_file() else ""
    ingest_run = read_json(artifacts / "ingest_run.json", default={}) or {}
    new_uniques = [item for item in uniques if item.get("dedup_key") not in existing_keys]
    report = render_report(
        host=identity.host,
        repo=identity.slug,
        base_branch=identity.base_branch or "main",
        cutoff=cutoff,
        last_pr=last_pr,
        comments=comments,
        uniques=uniques,
        new_uniques=new_uniques,
        previous_markdown=previous,
        include_run=bool(new_uniques) or bool(ingest_run.get("new")),
    )
    (artifacts / "REPORT.md").write_text(report, encoding="utf-8")
    checkpoint = read_checkpoint(artifacts / "checkpoint.json") or default_checkpoint(
        {
            "repo": identity.slug,
            "host": identity.host,
            "owner": identity.owner,
            "provider": identity.provider,
            "base_branch": identity.base_branch,
        }
    )
    checkpoint.update(
        {
            "repo": identity.slug,
            "host": identity.host,
            "owner": identity.owner,
            "provider": identity.provider,
            "base_branch": identity.base_branch,
            "last_run_at": now_iso(),
            "cutoff": cutoff,
            "last_pr_number": last_pr,
            "comment_count": len(comments),
            "unique_count": len(uniques),
        }
    )
    write_checkpoint(artifacts / "checkpoint.json", checkpoint)
    if ingest_run.get("new"):
        ingest_run["new"] = []
        ingest_run["processed_at"] = now_iso()
        write_json(artifacts / "ingest_run.json", ingest_run)
    return {
        "artifact_dir": artifacts,
        "uniques": uniques,
        "new_uniques": new_uniques,
        "comments": comments,
        "checkpoint": checkpoint,
        "changed": changed,
    }


def generate(identity: RepoIdentity) -> dict[str, Any]:
    artifacts = artifact_dir(identity.git_root, identity.host, identity.owner, identity.repo)
    uniques = read_json(artifacts / "unique.json", default=[]) or []
    stats = update_derived_skills(identity.git_root, uniques)
    checkpoint = read_checkpoint(artifacts / "checkpoint.json") or default_checkpoint()
    checkpoint["last_generated_at"] = now_iso()
    write_checkpoint(artifacts / "checkpoint.json", checkpoint)
    return {"stats": stats, "unique_count": len(uniques)}


def orchestrate(
    git_dir: str | Path | None = None,
    host: str | None = None,
    repo: str | None = None,
    base_branch: str | None = None,
    local_json: str | Path | None = None,
    skip_mirror: bool = False,
    runner=None,
) -> dict[str, Any]:
    identity = resolve_identity(git_dir, host, repo, base_branch, local_json, runner=runner)
    ingested = ingest(identity, local_json=local_json, runner=runner)
    refined = refine(identity)
    generated = generate(identity)
    mirrored = [] if skip_mirror else mirror_skills(identity.git_root)
    return {
        "identity": {
            "provider": identity.provider,
            "host": identity.host,
            "repo": identity.slug,
            "base_branch": identity.base_branch,
            "git_root": str(identity.git_root),
        },
        "new_comments": len(ingested["new_records"]),
        "total_comments": len(ingested["all_comments"]),
        "unique_comments": len(refined["uniques"]),
        "new_uniques": len(refined["new_uniques"]),
        "generate": generated["stats"],
        "mirrored": mirrored,
        "artifact_dir": str(ingested["artifact_dir"]),
    }
