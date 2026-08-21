"""GitLab adapter using `glab` or the REST API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..normalize import author_type_from, make_record
from ..proc import env_token, http_get_json, parse_next_link, run_json, which
from ..timeutil import is_after
from . import Adapter, IngestRequest, PullRequest, register


def _author(note: dict[str, Any]) -> tuple[str | None, str | None]:
    user = note.get("author") or note.get("user") or {}
    if isinstance(user, str):
        return user, None
    return user.get("username") or user.get("name"), user.get("bot") and "Bot" or user.get("type")


def records_from_discussions(
    host: str,
    repo: str,
    pr: PullRequest,
    discussions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for discussion in discussions:
        thread_id = discussion.get("id")
        for note in discussion.get("notes") or []:
            if note.get("system"):
                continue
            login, type_name = _author(note)
            position = note.get("position") or {}
            path = position.get("new_path") or position.get("old_path") or note.get("file_path")
            line = position.get("new_line") or position.get("old_line") or note.get("line_code")
            if isinstance(line, str):
                line = None
            kind = "diff_note" if note.get("type") == "DiffNote" or path else "note"
            out.append(
                make_record(
                    provider="gitlab",
                    host=host,
                    repo=repo,
                    pr_number=pr.number,
                    pr_title=pr.title,
                    kind=kind,
                    comment_id=note.get("id"),
                    thread_id=thread_id or note.get("id"),
                    author=login,
                    author_type=author_type_from(login, "Bot" if note.get("author", {}).get("bot") else type_name),
                    created_at=note.get("created_at"),
                    updated_at=note.get("updated_at"),
                    body=note.get("body") or "",
                    path=path,
                    line=line,
                    url=note.get("web_url") or pr.url,
                    in_reply_to=None,
                )
            )
    return out


def records_from_notes(
    host: str,
    repo: str,
    pr: PullRequest,
    notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    discussions = [{"id": note.get("id"), "notes": [note]} for note in notes]
    return records_from_discussions(host, repo, pr, discussions)


class GitLabAdapter(Adapter):
    name = "gitlab"

    def default_branch(self, request: IngestRequest) -> str | None:
        ident = request.identity
        if which("glab"):
            try:
                data = run_json(
                    request.runner,
                    ["glab", "repo", "view", ident.slug, "-F", "json"],
                    ident.git_root,
                )
                return (data or {}).get("default_branch")
            except SystemExit:
                return None
        return None

    def fetch(self, request: IngestRequest) -> list[dict[str, Any]]:
        prs = self._list_mrs(request)
        records: list[dict[str, Any]] = []
        for pr in prs:
            for record in self._fetch_mr_comments(request, pr):
                if request.cutoff and not is_after(record.get("created_at"), request.cutoff):
                    continue
                records.append(record)
        return records

    def _project(self, ident) -> str:
        return quote(ident.slug, safe="")

    def _list_mrs(self, request: IngestRequest) -> list[PullRequest]:
        ident = request.identity
        if which("glab"):
            args = [
                "glab",
                "mr",
                "list",
                "--repo",
                ident.slug,
                "--target-branch",
                request.base_branch,
                "--all",
                "-F",
                "json",
                "--per-page",
                "100",
            ]
            raw = run_json(request.runner, args, ident.git_root) or []
            if isinstance(raw, dict):
                raw = raw.get("items") or []
            return [_mr_from_api(item) for item in raw]
        return self._list_mrs_rest(request)

    def _list_mrs_rest(self, request: IngestRequest) -> list[PullRequest]:
        ident = request.identity
        token = env_token("GITLAB_TOKEN", "GL_TOKEN")
        if not token:
            raise SystemExit("GitLab adapter needs `glab` or GITLAB_TOKEN")
        api = f"https://{ident.host}/api/v4"
        url = (
            f"{api}/projects/{self._project(ident)}/merge_requests"
            f"?target_branch={quote(request.base_branch)}&state=all&per_page=100&order_by=updated_at&sort=desc"
        )
        if request.cutoff:
            url += f"&updated_after={quote(request.cutoff)}"
        headers = {"PRIVATE-TOKEN": token}
        items: list[Any] = []
        while url:
            data, link = http_get_json(url, headers=headers)
            items.extend(data or [])
            url = parse_next_link(link)
        return [_mr_from_api(item) for item in items]

    def _fetch_mr_comments(self, request: IngestRequest, pr: PullRequest) -> list[dict[str, Any]]:
        ident = request.identity
        if which("glab"):
            data = (
                run_json(
                    request.runner,
                    [
                        "glab",
                        "api",
                        f"projects/{self._project(ident)}/merge_requests/{pr.number}/discussions",
                    ],
                    ident.git_root,
                )
                or []
            )
            if isinstance(data, dict):
                data = [data]
            return records_from_discussions(ident.host, ident.slug, pr, data)
        token = env_token("GITLAB_TOKEN", "GL_TOKEN")
        api = f"https://{ident.host}/api/v4"
        url = f"{api}/projects/{self._project(ident)}/merge_requests/{pr.number}/discussions?per_page=100"
        headers = {"PRIVATE-TOKEN": token or ""}
        items: list[Any] = []
        while url:
            data, link = http_get_json(url, headers=headers)
            items.extend(data or [])
            url = parse_next_link(link)
        return records_from_discussions(ident.host, ident.slug, pr, items)


def _mr_from_api(item: dict[str, Any]) -> PullRequest:
    author = item.get("author") or {}
    return PullRequest(
        number=int(item.get("iid") or item.get("number")),
        title=item.get("title") or "",
        state=item.get("state") or "",
        url=item.get("web_url") or item.get("url"),
        created_at=item.get("created_at"),
        updated_at=item.get("updated_at"),
        merged_at=item.get("merged_at"),
        author=author.get("username") if isinstance(author, dict) else author,
    )


register(GitLabAdapter())
