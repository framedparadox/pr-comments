"""GitHub adapter using `gh` or the REST API."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from ..normalize import author_type_from, make_record
from ..proc import env_token, http_get_json, parse_next_link, run_json, which
from ..timeutil import is_after
from . import Adapter, IngestRequest, PullRequest, register


def _login(user: Any) -> tuple[str | None, str | None]:
    if user is None:
        return None, None
    if isinstance(user, str):
        return user, None
    return user.get("login") or user.get("name"), user.get("type")


def records_from_issue_comments(
    host: str,
    repo: str,
    pr: PullRequest,
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for item in comments:
        login, type_name = _login(item.get("user"))
        out.append(
            make_record(
                provider="github",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                kind="issue_comment",
                comment_id=item.get("id"),
                thread_id=item.get("id"),
                author=login,
                author_type=author_type_from(login, type_name, item.get("user") or {}),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                body=item.get("body") or "",
                url=item.get("html_url"),
            )
        )
    return out


def records_from_review_comments(
    host: str,
    repo: str,
    pr: PullRequest,
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for item in comments:
        login, type_name = _login(item.get("user"))
        out.append(
            make_record(
                provider="github",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                kind="review_comment",
                comment_id=item.get("id"),
                thread_id=item.get("in_reply_to_id") or item.get("pull_request_review_id") or item.get("id"),
                author=login,
                author_type=author_type_from(login, type_name, item.get("user") or {}),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                body=item.get("body") or "",
                path=item.get("path"),
                line=item.get("line") or item.get("original_line"),
                side=item.get("side"),
                url=item.get("html_url"),
                in_reply_to=item.get("in_reply_to_id"),
            )
        )
    return out


def records_from_reviews(
    host: str,
    repo: str,
    pr: PullRequest,
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for item in reviews:
        body = item.get("body") or ""
        if not body.strip():
            continue
        login, type_name = _login(item.get("user"))
        out.append(
            make_record(
                provider="github",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                kind="review_summary",
                comment_id=item.get("id"),
                thread_id=item.get("id"),
                author=login,
                author_type=author_type_from(login, type_name, item.get("user") or {}),
                created_at=item.get("submitted_at") or item.get("created_at"),
                updated_at=item.get("submitted_at") or item.get("created_at"),
                body=body,
                url=item.get("html_url"),
            )
        )
    return out


def records_from_pr_bundle(
    host: str,
    repo: str,
    pr: PullRequest,
    issue_comments: list[dict[str, Any]],
    review_comments: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return (
        records_from_issue_comments(host, repo, pr, issue_comments)
        + records_from_review_comments(host, repo, pr, review_comments)
        + records_from_reviews(host, repo, pr, reviews)
    )


class GitHubAdapter(Adapter):
    name = "github"

    def default_branch(self, request: IngestRequest) -> str | None:
        ident = request.identity
        if which("gh"):
            try:
                data = run_json(
                    request.runner,
                    [
                        "gh",
                        "repo",
                        "view",
                        ident.slug,
                        "--json",
                        "defaultBranchRef",
                    ],
                    ident.git_root,
                )
                ref = (data or {}).get("defaultBranchRef") or {}
                return ref.get("name")
            except SystemExit:
                return None
        return None

    def fetch(self, request: IngestRequest) -> list[dict[str, Any]]:
        prs = self._list_prs(request)
        records: list[dict[str, Any]] = []
        for pr in prs:
            bundle = self._fetch_pr_comments(request, pr)
            for record in bundle:
                if request.cutoff and not is_after(record.get("created_at"), request.cutoff):
                    continue
                records.append(record)
        return records

    def _list_prs(self, request: IngestRequest) -> list[PullRequest]:
        ident = request.identity
        if which("gh"):
            args = [
                "gh",
                "pr",
                "list",
                "--repo",
                ident.slug,
                "--base",
                request.base_branch,
                "--state",
                "all",
                "--limit",
                "1000",
                "--json",
                "number,title,author,createdAt,updatedAt,mergedAt,state,url",
            ]
            if request.cutoff:
                args.extend(["--search", f"updated:>={request.cutoff[:10]}"])
            raw = run_json(request.runner, args, ident.git_root) or []
            return [
                PullRequest(
                    number=int(item["number"]),
                    title=item.get("title") or "",
                    state=item.get("state") or "",
                    url=item.get("url"),
                    created_at=item.get("createdAt"),
                    updated_at=item.get("updatedAt"),
                    merged_at=item.get("mergedAt"),
                    author=(item.get("author") or {}).get("login") if isinstance(item.get("author"), dict) else item.get("author"),
                )
                for item in raw
            ]
        return self._list_prs_rest(request)

    def _list_prs_rest(self, request: IngestRequest) -> list[PullRequest]:
        ident = request.identity
        token = env_token("GH_TOKEN", "GITHUB_TOKEN")
        if not token:
            raise SystemExit("GitHub adapter needs `gh` or GH_TOKEN/GITHUB_TOKEN")
        host = ident.host
        api = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
        url = (
            f"{api}/repos/{ident.slug}/pulls?state=all&base={quote(request.base_branch)}"
            f"&per_page=100&sort=updated&direction=desc"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        items: list[Any] = []
        while url:
            data, link = http_get_json(url, headers=headers)
            items.extend(data or [])
            url = parse_next_link(link)
        prs = []
        for item in items:
            updated = item.get("updated_at")
            if request.cutoff and updated and not is_after(updated, request.cutoff):
                # remaining pages are older because of sort=updated desc
                break
            user = item.get("user") or {}
            prs.append(
                PullRequest(
                    number=int(item["number"]),
                    title=item.get("title") or "",
                    state=item.get("state") or "",
                    url=item.get("html_url"),
                    created_at=item.get("created_at"),
                    updated_at=updated,
                    merged_at=item.get("merged_at"),
                    author=user.get("login"),
                )
            )
        return prs

    def _fetch_pr_comments(self, request: IngestRequest, pr: PullRequest) -> list[dict[str, Any]]:
        ident = request.identity
        if which("gh"):
            issue = (
                run_json(
                    request.runner,
                    ["gh", "api", "--paginate", f"repos/{ident.slug}/issues/{pr.number}/comments"],
                    ident.git_root,
                )
                or []
            )
            review_comments = (
                run_json(
                    request.runner,
                    ["gh", "api", "--paginate", f"repos/{ident.slug}/pulls/{pr.number}/comments"],
                    ident.git_root,
                )
                or []
            )
            reviews = (
                run_json(
                    request.runner,
                    ["gh", "api", "--paginate", f"repos/{ident.slug}/pulls/{pr.number}/reviews"],
                    ident.git_root,
                )
                or []
            )
            if isinstance(issue, dict):
                issue = [issue]
            if isinstance(review_comments, dict):
                review_comments = [review_comments]
            if isinstance(reviews, dict):
                reviews = [reviews]
            return records_from_pr_bundle(ident.host, ident.slug, pr, issue, review_comments, reviews)
        return self._fetch_pr_comments_rest(request, pr)

    def _fetch_pr_comments_rest(self, request: IngestRequest, pr: PullRequest) -> list[dict[str, Any]]:
        ident = request.identity
        token = env_token("GH_TOKEN", "GITHUB_TOKEN")
        host = ident.host
        api = "https://api.github.com" if host == "github.com" else f"https://{host}/api/v3"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        def all_pages(path: str) -> list[dict[str, Any]]:
            url = f"{api}/repos/{ident.slug}/{path}?per_page=100"
            out: list[dict[str, Any]] = []
            while url:
                data, link = http_get_json(url, headers=headers)
                out.extend(data or [])
                url = parse_next_link(link)
            return out

        return records_from_pr_bundle(
            ident.host,
            ident.slug,
            pr,
            all_pages(f"issues/{pr.number}/comments"),
            all_pages(f"pulls/{pr.number}/comments"),
            all_pages(f"pulls/{pr.number}/reviews"),
        )


register(GitHubAdapter())
