"""GitHub pull-request comment fetch via `gh` or the REST API.

Keeps conversation comments, inline review comments (including replies),
and non-empty review summaries. Authors that GitHub later deleted appear as
`ghost` with `author_type=deleted` — they are not filtered out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlencode

from .normalize import author_type_from, login_from_user, make_row, number_from_url
from .proc import Runner, default_runner, env_token, http_get_json, parse_next_link, run_json, which


@dataclass
class PullRequest:
    number: int
    title: str
    state: str
    url: str | None
    created_at: str | None
    updated_at: str | None = None
    merged_at: str | None = None
    author: str | None = None
    head_sha: str | None = None
    merge_commit_sha: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


Transport = Callable[[str], Any]


def _user_fields(item: dict[str, Any]) -> tuple[str | None, str]:
    login, type_name = login_from_user(item.get("user"))
    return login, author_type_from(login, type_name, item.get("user") or {})


def pull_request_from_api(item: dict[str, Any]) -> PullRequest:
    user = item.get("user") or item.get("author") or {}
    if isinstance(user, str):
        login = user
    else:
        login = user.get("login") or user.get("name")
    head = item.get("head") or {}
    html_url = item.get("html_url") or item.get("url")
    state = (item.get("state") or "").lower()
    if item.get("merged_at") or item.get("mergedAt"):
        state = "merged"
    return PullRequest(
        number=int(item["number"]),
        title=item.get("title") or "",
        state=state,
        url=html_url,
        created_at=item.get("created_at") or item.get("createdAt"),
        updated_at=item.get("updated_at") or item.get("updatedAt"),
        merged_at=item.get("merged_at") or item.get("mergedAt"),
        author=login,
        head_sha=(head.get("sha") if isinstance(head, dict) else None) or item.get("headRefOid"),
        merge_commit_sha=item.get("merge_commit_sha") or item.get("mergeCommitSha"),
    )


def records_from_issue_comments(
    host: str,
    repo: str,
    prs: dict[int, PullRequest],
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in comments:
        number = number_from_url(item.get("issue_url") or item.get("html_url"))
        if number is None:
            continue
        pr = prs.get(number)
        if pr is None:
            continue
        login, author_type = _user_fields(item)
        out.append(
            make_row(
                provider="github",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                pr_state=pr.state,
                pr_created_at=pr.created_at,
                pr_merged_at=pr.merged_at,
                pr_author=pr.author,
                pr_url=pr.url,
                pr_head_sha=pr.head_sha,
                merge_commit_sha=pr.merge_commit_sha,
                kind="conversation",
                native_id=item.get("id"),
                commit_id=item.get("commit_id") or "",
                comment_date=item.get("created_at"),
                comment_updated_at=item.get("updated_at"),
                author=login,
                author_type=author_type,
                body=item.get("body") or "",
                url=item.get("html_url"),
            )
        )
    return out


def records_from_review_comments(
    host: str,
    repo: str,
    prs: dict[int, PullRequest],
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in comments:
        number = number_from_url(
            item.get("pull_request_url") or item.get("html_url") or item.get("url")
        )
        if number is None:
            continue
        pr = prs.get(number)
        if pr is None:
            continue
        login, author_type = _user_fields(item)
        native_id = item.get("id")
        reply_to = item.get("in_reply_to_id")
        out.append(
            make_row(
                provider="github",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                pr_state=pr.state,
                pr_created_at=pr.created_at,
                pr_merged_at=pr.merged_at,
                pr_author=pr.author,
                pr_url=pr.url,
                pr_head_sha=pr.head_sha,
                merge_commit_sha=pr.merge_commit_sha,
                kind="inline_review",
                native_id=native_id,
                commit_id=item.get("commit_id") or pr.head_sha,
                original_commit_id=item.get("original_commit_id"),
                comment_date=item.get("created_at"),
                comment_updated_at=item.get("updated_at"),
                author=login,
                author_type=author_type,
                body=item.get("body") or "",
                path=item.get("path"),
                line=item.get("line") or item.get("original_line"),
                side=item.get("side") or item.get("original_side"),
                url=item.get("html_url"),
                in_reply_to=reply_to,
                thread_id=reply_to or native_id,
                diff_hunk=item.get("diff_hunk"),
            )
        )
    return out


def records_from_reviews(
    host: str,
    repo: str,
    pr: PullRequest,
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in reviews:
        body = item.get("body") or ""
        if not str(body).strip():
            continue
        login, author_type = _user_fields(item)
        out.append(
            make_row(
                provider="github",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                pr_state=pr.state,
                pr_created_at=pr.created_at,
                pr_merged_at=pr.merged_at,
                pr_author=pr.author,
                pr_url=pr.url,
                pr_head_sha=pr.head_sha,
                merge_commit_sha=pr.merge_commit_sha,
                kind="review_summary",
                native_id=item.get("id"),
                commit_id=item.get("commit_id") or pr.head_sha,
                comment_date=item.get("submitted_at") or item.get("created_at"),
                comment_updated_at=item.get("submitted_at") or item.get("created_at"),
                author=login,
                author_type=author_type,
                body=body,
                url=item.get("html_url"),
            )
        )
    return out


class GitHubExtractor:
    def __init__(
        self,
        host: str,
        slug: str,
        *,
        runner: Runner = default_runner,
        cwd=None,
        transport: Transport | None = None,
        token: str | None = None,
    ) -> None:
        self.host = host
        self.slug = slug
        self.runner = runner
        self.cwd = cwd
        self.transport = transport
        self.token = token or env_token("GH_TOKEN", "GITHUB_TOKEN")

    def default_branch(self) -> str | None:
        if self.transport:
            data = self.transport(f"repos/{self.slug}")
            return ((data or {}).get("default_branch")) if isinstance(data, dict) else None
        if which("gh"):
            try:
                args = ["gh", "repo", "view", self.slug, "--json", "defaultBranchRef"]
                if self.host and self.host != "github.com":
                    args.extend(["--hostname", self.host])
                data = run_json(self.runner, args, self.cwd) or {}
                ref = data.get("defaultBranchRef") or {}
                return ref.get("name")
            except SystemExit:
                return None
        data = self._rest_one(f"repos/{self.slug}")
        if isinstance(data, dict):
            return data.get("default_branch")
        return None

    def list_pull_requests(self, base_branch: str) -> list[PullRequest]:
        query = urlencode({"state": "all", "base": base_branch, "per_page": "100", "sort": "created", "direction": "asc"})
        raw = self._paginate(f"repos/{self.slug}/pulls?{query}")
        return [pull_request_from_api(item) for item in raw if item.get("number") is not None]

    def fetch_comments(
        self,
        prs: list[PullRequest],
        *,
        include_reviews: bool = True,
    ) -> list[dict[str, Any]]:
        by_number = {pr.number: pr for pr in prs}
        if not by_number:
            return []
        issue_comments = self._paginate(f"repos/{self.slug}/issues/comments?per_page=100")
        review_comments = self._paginate(f"repos/{self.slug}/pulls/comments?per_page=100")
        records = records_from_issue_comments(self.host, self.slug, by_number, issue_comments)
        records.extend(records_from_review_comments(self.host, self.slug, by_number, review_comments))
        if include_reviews:
            for pr in prs:
                reviews = self._paginate(f"repos/{self.slug}/pulls/{pr.number}/reviews?per_page=100")
                records.extend(records_from_reviews(self.host, self.slug, pr, reviews))
        records.sort(key=lambda row: (row.get("pr_number") or 0, row.get("comment_date") or "", row.get("id") or ""))
        return records

    def _paginate(self, path: str) -> list[dict[str, Any]]:
        if self.transport:
            data = self.transport(path)
            if data is None:
                return []
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            return []
        if which("gh"):
            return self._gh_paginate(path)
        return self._rest_paginate(path)

    def _rest_one(self, path: str) -> Any:
        if self.transport:
            return self.transport(path)
        token = self.token
        if not token:
            raise SystemExit("GitHub access needs `gh` or GH_TOKEN/GITHUB_TOKEN")
        url = self._api_url(path)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        data, _ = http_get_json(url, headers=headers)
        return data

    def _gh_paginate(self, path: str) -> list[dict[str, Any]]:
        args = ["gh", "api", "--paginate", path]
        if self.host and self.host != "github.com":
            args = ["gh", "api", "--hostname", self.host, "--paginate", path]
        data = run_json(self.runner, args, self.cwd)
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    def _rest_paginate(self, path: str) -> list[dict[str, Any]]:
        token = self.token
        if not token:
            raise SystemExit("GitHub access needs `gh` or GH_TOKEN/GITHUB_TOKEN")
        url = self._api_url(path)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        items: list[Any] = []
        while url:
            data, link = http_get_json(url, headers=headers)
            if isinstance(data, list):
                items.extend(data)
            elif data:
                items.append(data)
            url = parse_next_link(link)
        return items

    def _api_url(self, path: str) -> str:
        path = path.lstrip("/")
        if self.host == "github.com":
            return f"https://api.github.com/{path}"
        return f"https://{self.host}/api/v3/{path}"
