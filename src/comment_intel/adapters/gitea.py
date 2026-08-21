"""Gitea / Forgejo REST adapter (GitHub-like)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..normalize import author_type_from, make_record
from ..proc import env_token, http_get_json
from ..timeutil import is_after
from . import Adapter, IngestRequest, PullRequest, register


def records_from_issue_comments(host: str, repo: str, pr: PullRequest, comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in comments:
        user = item.get("user") or {}
        login = user.get("login") or user.get("username")
        out.append(
            make_record(
                provider="gitea",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                kind="issue_comment",
                comment_id=item.get("id"),
                thread_id=item.get("id"),
                author=login,
                author_type=author_type_from(login, user.get("type") or ("Bot" if user.get("is_bot") else None)),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                body=item.get("body") or "",
                url=item.get("html_url"),
            )
        )
    return out


def records_from_review_comments(host: str, repo: str, pr: PullRequest, comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in comments:
        user = item.get("user") or {}
        login = user.get("login") or user.get("username")
        out.append(
            make_record(
                provider="gitea",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                kind="review_comment",
                comment_id=item.get("id"),
                thread_id=item.get("pull_request_review_id") or item.get("id"),
                author=login,
                author_type=author_type_from(login, user.get("type")),
                created_at=item.get("created_at") or item.get("updated_at"),
                updated_at=item.get("updated_at"),
                body=item.get("body") or "",
                path=item.get("path"),
                line=item.get("line") or item.get("position"),
                side=item.get("side"),
                url=item.get("html_url"),
                in_reply_to=item.get("in_reply_to_id"),
            )
        )
    return out


class GiteaAdapter(Adapter):
    name = "gitea"

    def fetch(self, request: IngestRequest) -> list[dict[str, Any]]:
        ident = request.identity
        token = env_token("GITEA_TOKEN", "FORGEJO_TOKEN")
        if not token:
            raise SystemExit("Gitea/Forgejo adapter needs GITEA_TOKEN (or FORGEJO_TOKEN)")
        headers = {"Authorization": f"token {token}"}
        api = f"https://{ident.host}/api/v1/repos/{ident.slug}"
        url = f"{api}/pulls?state=all&base={quote(request.base_branch)}&limit=50&page=1"
        prs: list[PullRequest] = []
        page = 1
        while True:
            data, _ = http_get_json(f"{api}/pulls?state=all&limit=50&page={page}", headers=headers)
            if not data:
                break
            for item in data:
                base = ((item.get("base") or {}).get("ref"))
                if base and base != request.base_branch:
                    continue
                updated = item.get("updated_at")
                if request.cutoff and updated and not is_after(updated, request.cutoff):
                    continue
                user = item.get("user") or {}
                prs.append(
                    PullRequest(
                        number=int(item.get("number")),
                        title=item.get("title") or "",
                        state=item.get("state") or "",
                        url=item.get("html_url"),
                        created_at=item.get("created_at"),
                        updated_at=updated,
                        merged_at=item.get("merged_at"),
                        author=user.get("login"),
                    )
                )
            if len(data) < 50:
                break
            page += 1
        records: list[dict[str, Any]] = []
        for pr in prs:
            issue, _ = http_get_json(f"{api}/issues/{pr.number}/comments", headers=headers)
            review, _ = http_get_json(f"{api}/pulls/{pr.number}/comments", headers=headers)
            bundle = records_from_issue_comments(ident.host, ident.slug, pr, issue or [])
            bundle += records_from_review_comments(ident.host, ident.slug, pr, review or [])
            for record in bundle:
                if request.cutoff and not is_after(record.get("created_at"), request.cutoff):
                    continue
                records.append(record)
        return records


register(GiteaAdapter())
