"""Bitbucket Cloud REST adapter."""

from __future__ import annotations

from typing import Any

from ..normalize import author_type_from, make_record
from ..proc import env_token, http_get_json
from ..timeutil import is_after
from . import Adapter, IngestRequest, PullRequest, register


def records_from_comments(
    host: str,
    repo: str,
    pr: PullRequest,
    comments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = []
    for item in comments:
        user = item.get("user") or {}
        login = user.get("nickname") or user.get("display_name") or user.get("uuid")
        inline = item.get("inline") or {}
        content = item.get("content") or {}
        body = content.get("raw") or content.get("markup") or item.get("body") or ""
        parent = (item.get("parent") or {}).get("id")
        out.append(
            make_record(
                provider="bitbucket",
                host=host,
                repo=repo,
                pr_number=pr.number,
                pr_title=pr.title,
                kind="diff_note" if inline.get("path") else "note",
                comment_id=item.get("id"),
                thread_id=parent or item.get("id"),
                author=login,
                author_type=author_type_from(login, user.get("type")),
                created_at=item.get("created_on"),
                updated_at=item.get("updated_on"),
                body=body,
                path=inline.get("path"),
                line=inline.get("to") or inline.get("from"),
                url=(item.get("links") or {}).get("html", {}).get("href") or pr.url,
                in_reply_to=parent,
            )
        )
    return out


class BitbucketAdapter(Adapter):
    name = "bitbucket"

    def fetch(self, request: IngestRequest) -> list[dict[str, Any]]:
        ident = request.identity
        token = env_token("BITBUCKET_TOKEN", "BITBUCKET_ACCESS_TOKEN")
        if not token:
            raise SystemExit("Bitbucket adapter needs BITBUCKET_TOKEN")
        headers = {"Authorization": f"Bearer {token}"}
        api = f"https://api.bitbucket.org/2.0/repositories/{ident.slug}/pullrequests"
        url = f"{api}?pagelen=50"
        prs: list[PullRequest] = []
        while url:
            data, _ = http_get_json(url, headers=headers)
            for item in data.get("values") or []:
                dest = ((item.get("destination") or {}).get("branch") or {}).get("name")
                if dest and dest != request.base_branch:
                    continue
                updated = item.get("updated_on")
                if request.cutoff and updated and not is_after(updated, request.cutoff):
                    continue
                author = item.get("author") or {}
                prs.append(
                    PullRequest(
                        number=int(item["id"]),
                        title=item.get("title") or "",
                        state=item.get("state") or "",
                        url=(item.get("links") or {}).get("html", {}).get("href"),
                        created_at=item.get("created_on"),
                        updated_at=updated,
                        author=author.get("nickname") or author.get("display_name"),
                    )
                )
            url = data.get("next")
        records: list[dict[str, Any]] = []
        for pr in prs:
            curl = f"{api}/{pr.number}/comments?pagelen=100"
            comments: list[dict[str, Any]] = []
            while curl:
                data, _ = http_get_json(curl, headers=headers)
                comments.extend(data.get("values") or [])
                curl = data.get("next")
            for record in records_from_comments(ident.host, ident.slug, pr, comments):
                if request.cutoff and not is_after(record.get("created_at"), request.cutoff):
                    continue
                records.append(record)
        return records


register(BitbucketAdapter())
