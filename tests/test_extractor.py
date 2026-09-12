from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_comments.cli import main
from pr_comments.detect import (
    RepoIdentity,
    parse_remote_url,
    parse_repo_slug,
    provider_from_host,
    resolve_base_branch,
)
from pr_comments.export import csv_safe, write_csv
from pr_comments.extract import extract
from pr_comments.github import (
    GitHubExtractor,
    records_from_issue_comments,
    records_from_review_comments,
    records_from_reviews,
    pull_request_from_api,
)
from pr_comments.normalize import author_type_from, number_from_url
from pr_comments.paths import default_output_dir
from pr_comments.proc import env_token, parse_cli_json, parse_next_link
from pr_comments.schema import CSV_FIELDS, JSON_EXTRA_FIELDS
from pr_comments.serve import make_server, serve

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _prs():
    return {item["number"]: pull_request_from_api(item) for item in _load("github_pulls.json")}


def _fixture_transport(calls: list[str] | None = None):
    pulls = _load("github_pulls.json")
    issues = _load("github_issue_comments.json")
    reviews_c = _load("github_review_comments.json")
    reviews = _load("github_reviews.json")

    def transport(path: str):
        if calls is not None:
            calls.append(path)
        base = path.split("?", 1)[0]
        if base.endswith("/acme/app") and "/pulls" not in base and "/issues" not in base:
            return _load("github_repo.json")
        if "/pulls/" in base and base.endswith("/reviews"):
            number = int(base.rsplit("/", 2)[1])
            return [
                r
                for r in reviews
                if (number == 150 and r["id"] in {9001, 9002}) or (number == 148 and r["id"] == 8800)
            ]
        if base.endswith("/pulls/comments"):
            return reviews_c
        if base.endswith("/issues/comments"):
            return issues
        if base.endswith("/pulls"):
            return pulls
        raise AssertionError(path)

    return transport


class DetectTests(unittest.TestCase):
    def test_parse_github_ssh(self):
        provider, host, owner, repo = parse_remote_url("git@github.com:framedparadox/pr-comments.git")
        self.assertEqual((provider, host, owner, repo), ("github", "github.com", "framedparadox", "pr-comments"))

    def test_parse_https_with_token(self):
        url = "https://x-access-token:ghs_secret@github.com/acme/app.git"
        provider, host, owner, repo = parse_remote_url(url)
        self.assertEqual((provider, host, owner, repo), ("github", "github.com", "acme", "app"))

    def test_parse_repo_slug(self):
        provider, host, owner, repo = parse_repo_slug("acme/app")
        self.assertEqual((provider, host, owner, repo), ("github", "github.com", "acme", "app"))

    def test_provider_github_enterprise(self):
        self.assertEqual(provider_from_host("github.example.com"), "github")


class NormalizeTests(unittest.TestCase):
    def test_ghost_user_is_deleted(self):
        self.assertEqual(author_type_from(None, None, {}), "deleted")
        self.assertEqual(author_type_from("ghost", "User"), "deleted")

    def test_bot_login(self):
        self.assertEqual(author_type_from("dependabot[bot]", "Bot"), "bot")

    def test_number_from_issue_url(self):
        self.assertEqual(number_from_url("https://api.github.com/repos/acme/app/issues/150"), 150)
        self.assertEqual(number_from_url("https://api.github.com/repos/acme/app/pulls/148"), 148)


class AdapterTests(unittest.TestCase):
    def test_keeps_deactivated_conversation_comment(self):
        rows = records_from_issue_comments("github.com", "acme/app", _prs(), _load("github_issue_comments.json"))
        ghost = next(r for r in rows if r["native_id"] == "9933")
        self.assertEqual(ghost["comment_by"], "ghost")
        self.assertEqual(ghost["author_type"], "deleted")
        self.assertIn("changelog", ghost["comment"])
        self.assertEqual(ghost["pr_number"], 148)
        self.assertEqual(ghost["pr_created_at"], "2026-07-01T00:00:00Z")

    def test_drops_plain_issue_comments(self):
        rows = records_from_issue_comments("github.com", "acme/app", _prs(), _load("github_issue_comments.json"))
        self.assertFalse(any(r["native_id"] == "9999" for r in rows))

    def test_inline_commit_and_reply(self):
        rows = records_from_review_comments("github.com", "acme/app", _prs(), _load("github_review_comments.json"))
        root = next(r for r in rows if r["native_id"] == "48212")
        reply = next(r for r in rows if r["native_id"] == "48214")
        self.assertEqual(root["commit_id"], "aaa111bbb222ccc333ddd444eee555fff666aaa1")
        self.assertEqual(root["comment_kind"], "inline_review")
        self.assertEqual(root["path"], "auth.py")
        self.assertEqual(root["line"], 112)
        self.assertTrue(reply["is_reply"])
        self.assertEqual(reply["in_reply_to"], "48212")
        self.assertEqual(reply["thread_id"], "48212")

    def test_review_summary_skips_empty_and_keeps_ghost(self):
        prs = _prs()
        rows = records_from_reviews(
            "github.com",
            "acme/app",
            prs[148],
            [item for item in _load("github_reviews.json") if item["id"] in {8800, 9002}],
        )
        self.assertEqual(len(rows), 1)
        ghost = rows[0]
        self.assertEqual(ghost["native_id"], "8800")
        self.assertEqual(ghost["comment_by"], "ghost")
        self.assertEqual(ghost["commit_id"], "bbb222ccc333ddd444eee555fff666aaa111bbb2")

    def test_merged_pr_state(self):
        pr = pull_request_from_api(_load("github_pulls.json")[1])
        self.assertEqual(pr.state, "merged")


class TransportExtractTests(unittest.TestCase):
    def test_extract_writes_csv_and_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export"
            result = extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=out,
                transport=_fixture_transport(),
            )
            self.assertGreaterEqual(result["comment_count"], 6)
            csv_path = Path(result["csv"])
            html_path = Path(result["dashboard"])
            self.assertTrue(csv_path.is_file())
            self.assertTrue(html_path.is_file())
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            fields = set(rows[0].keys())
            for required in ("commit_id", "pr_created_at", "comment_date", "comment_by", "comment"):
                self.assertIn(required, fields)
            authors = {row["comment_by"] for row in rows}
            self.assertIn("ghost", authors)
            self.assertIn("dependabot[bot]", authors)
            self.assertNotIn("eve", authors)
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("ghost", html)
            self.assertIn("Null check missing", html)
            self.assertIn("aaa111b", html)
            self.assertNotIn("targets develop", html)

    def test_since_filters_comment_date(self):
        def transport(path: str):
            base = path.split("?", 1)[0]
            if base.endswith("/pulls"):
                return _load("github_pulls.json")
            if base.endswith("/issues/comments"):
                return _load("github_issue_comments.json")
            if base.endswith("/pulls/comments"):
                return []
            if base.endswith("/reviews"):
                return []
            if base.endswith("/acme/app"):
                return {"default_branch": "main"}
            return []

        with tempfile.TemporaryDirectory() as tmp:
            result = extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=tmp,
                since="2026-08-01T00:00:00Z",
                transport=transport,
            )
            self.assertTrue(all(c["comment_date"] >= "2026-08-01" for c in json.loads(Path(result["json"]).read_text())))
            self.assertNotIn("ghost", {c["comment_by"] for c in json.loads(Path(result["json"]).read_text())})


class CsvTests(unittest.TestCase):
    def test_formula_injection_prefix(self):
        self.assertEqual(csv_safe("=cmd"), "'=cmd")
        self.assertEqual(csv_safe("hello"), "hello")

    def test_csv_column_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.csv"
            write_csv(path, [{"repo": "acme/app", "pr_number": 1, "comment": "hi", "comment_by": "a"}])
            header = path.read_text(encoding="utf-8-sig").splitlines()[0]
            self.assertEqual(header.split(",")[0], "repo")
            for field in CSV_FIELDS:
                self.assertIn(field, header)


class CliTests(unittest.TestCase):
    def test_local_json_extract(self):
        rows = records_from_issue_comments("github.com", "acme/app", _prs(), _load("github_issue_comments.json"))
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / "in.json"
            out = Path(tmp) / "out"
            dump.write_text(json.dumps(rows), encoding="utf-8")
            code = main(["extract", "--repo", "acme/app", "--local-json", str(dump), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue((out / "comments.csv").is_file())
            self.assertTrue((out / "dashboard.html").is_file())


class HatchLayoutTests(unittest.TestCase):
    def test_skills_exist(self):
        self.assertTrue((ROOT / "skills" / "extract-pr-comments" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "skills" / "review-pr-comments" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "src" / "pr_comments" / "dashboard.html").is_file())

    def test_does_not_ship_per_agent_skill_directories(self):
        self.assertFalse((ROOT / ".claude").exists())
        self.assertFalse((ROOT / ".agents").exists())
        self.assertFalse((ROOT / ".github" / "skills").exists())

    def test_cli_help_exposes_documented_flags(self):
        from pr_comments.cli import build_parser

        parser = build_parser()
        text = parser.format_help()
        self.assertIn("extract", text)
        self.assertIn("serve", text)
        extract_parser = serve_parser = None
        for action in parser._actions:
            if getattr(action, "dest", None) == "command":
                extract_parser = action.choices["extract"]
                serve_parser = action.choices["serve"]
        extract_flags = extract_parser.format_help()
        for flag in ("--repo", "--git-dir", "--host", "--base-branch", "--out", "--since"):
            self.assertIn(flag, extract_flags)
        self.assertIn("--out", serve_parser.format_help())
        self.assertIn("--port", serve_parser.format_help())

    def test_pyproject_includes_skills_in_the_wheel(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"skills" = "pr_comments/data/skills"', text)
        self.assertIn('pr-comments = "pr_comments.cli:main"', text)
        self.assertIn('license = { text = "MIT" }', text)
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["name"], "pr-comments")
        self.assertEqual(pkg["license"], "MIT")
        self.assertEqual(pkg["bin"]["pr-comments"], "bin/pr-comments.js")
        self.assertTrue(any(item.startswith("src/") for item in pkg["files"]))
        self.assertIn("LICENSE", pkg["files"])
        self.assertEqual(pkg["publishConfig"]["access"], "public")

    def test_skill_scripts_and_references_exist(self):
        extract_skill = ROOT / "skills" / "extract-pr-comments"
        review_skill = ROOT / "skills" / "review-pr-comments"
        self.assertTrue((extract_skill / "scripts" / "extract.py").is_file())
        self.assertTrue((review_skill / "scripts" / "serve.py").is_file())
        self.assertTrue((extract_skill / "references" / "fields.md").is_file())
        self.assertTrue((extract_skill / "references" / "sources.md").is_file())
        front = (extract_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: extract-pr-comments", front)
        self.assertIn("comment_by=ghost", front)


class ArtifactContractTests(unittest.TestCase):
    def test_extract_writes_every_documented_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export"
            result = extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=out,
                transport=_fixture_transport(),
            )
            for name in ("comments.csv", "comments.json", "comments.jsonl", "dashboard.html", "meta.json"):
                self.assertTrue((out / name).is_file(), name)
            csv_bytes = (out / "comments.csv").read_bytes()
            self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"), "CSV must be UTF-8 with BOM")
            with (out / "comments.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(rows[0].keys()), list(CSV_FIELDS))
            json_rows = json.loads((out / "comments.json").read_text(encoding="utf-8"))
            jsonl_rows = [
                json.loads(line)
                for line in (out / "comments.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(json_rows), len(jsonl_rows))
            inline = next(r for r in json_rows if r["native_id"] == "48212")
            for field in JSON_EXTRA_FIELDS:
                self.assertIn(field, inline)
            self.assertTrue(inline["diff_hunk"])
            meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["repo"], "acme/app")
            self.assertEqual(meta["host"], "github.com")
            self.assertEqual(meta["base_branch"], "main")
            self.assertEqual(meta["comment_count"], result["comment_count"])
            self.assertIn("extracted_at", meta)
            conversation = next(r for r in json_rows if r["comment_kind"] == "conversation")
            self.assertEqual(conversation["commit_id"], "")

    def test_default_output_directory_uses_host_owner_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = Path(tmp)
            path = default_output_dir(start, "github.com", "acme", "app")
            self.assertEqual(path, start.resolve() / "pr-comments-export" / "github.com--acme--app")

    def test_written_csv_neutralizes_formula_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.csv"
            write_csv(path, [{"repo": "acme/app", "pr_number": 1, "comment": "=cmd|'/c calc'!A0", "comment_by": "+evil"}])
            with path.open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertTrue(row["comment"].startswith("'="))
            self.assertTrue(row["comment_by"].startswith("'+"))


class PullRequestScopeTests(unittest.TestCase):
    def test_lists_all_states_on_base_branch_only(self):
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=tmp,
                transport=_fixture_transport(calls),
            )
            comments = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
        pulls_calls = [c for c in calls if "/pulls?" in c or c.split("?", 1)[0].endswith("/pulls")]
        self.assertTrue(pulls_calls)
        query = pulls_calls[0]
        self.assertIn("state=all", query)
        self.assertIn("base=main", query)
        pr_numbers = {c["pr_number"] for c in comments}
        self.assertIn(148, pr_numbers)
        self.assertIn(149, pr_numbers)
        self.assertIn(150, pr_numbers)
        self.assertNotIn(99, pr_numbers)
        states = {c["pr_state"] for c in comments}
        self.assertIn("open", states)
        self.assertIn("merged", states)
        self.assertIn("closed", states)
        kinds = {c["comment_kind"] for c in comments}
        self.assertEqual(kinds, {"conversation", "inline_review", "review_summary"})
        self.assertTrue(any(c["is_reply"] for c in comments))
        self.assertTrue(any(c["author_type"] == "bot" for c in comments))
        self.assertTrue(any(c["author_type"] == "deleted" for c in comments))
        self.assertEqual(result["pull_request_count"], 3)

    def test_closed_unmerged_pr_is_kept(self):
        prs = _prs()
        self.assertEqual(prs[149].state, "closed")
        self.assertIsNone(prs[149].merged_at)

    def test_gitlab_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                extract(repo="acme/app", host="gitlab.com", output_dir=tmp)


class GithubTransportTests(unittest.TestCase):
    def test_enterprise_api_url(self):
        extractor = GitHubExtractor("github.example.com", "acme/app")
        self.assertEqual(
            extractor._api_url("repos/acme/app/pulls"),
            "https://github.example.com/api/v3/repos/acme/app/pulls",
        )
        public = GitHubExtractor("github.com", "acme/app")
        self.assertEqual(public._api_url("repos/acme/app/pulls"), "https://api.github.com/repos/acme/app/pulls")

    def test_parse_next_link(self):
        header = '<https://api.github.com/repos/acme/app/pulls?page=2>; rel="next", <https://api.github.com/repos/acme/app/pulls?page=4>; rel="last"'
        self.assertEqual(
            parse_next_link(header),
            "https://api.github.com/repos/acme/app/pulls?page=2",
        )
        self.assertIsNone(parse_next_link(None))

    def test_parse_cli_json_concatenated_pages(self):
        data = parse_cli_json('[{"id":1}][{"id":2}]')
        self.assertEqual(data, [{"id": 1}, {"id": 2}])

    def test_env_token_prefers_gh_token(self):
        with patch.dict(os.environ, {"GH_TOKEN": "from-gh", "GITHUB_TOKEN": "from-github"}, clear=False):
            self.assertEqual(env_token("GH_TOKEN", "GITHUB_TOKEN"), "from-gh")

    def test_resolve_base_branch_order(self):
        identity = RepoIdentity(None, "github", "github.com", "acme", "app", None)
        self.assertEqual(resolve_base_branch(identity, requested="release"), "release")
        self.assertEqual(resolve_base_branch(identity, api_default="develop"), "develop")
        self.assertEqual(resolve_base_branch(identity), "main")

        def origin_head_runner(args, cwd=None):
            from subprocess import CompletedProcess

            if args[-2:] == ["symbolic-ref", "refs/remotes/origin/HEAD"]:
                return CompletedProcess(args, 0, "refs/remotes/origin/trunk\n", "")
            return CompletedProcess(args, 1, "", "")

        rooted = RepoIdentity(Path("."), "github", "github.com", "acme", "app", None)
        self.assertEqual(resolve_base_branch(rooted, runner=origin_head_runner), "trunk")


class DashboardAndServeTests(unittest.TestCase):
    def test_dashboard_embeds_data_and_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=tmp,
                transport=_fixture_transport(),
            )
            html = Path(result["dashboard"]).read_text(encoding="utf-8")
        self.assertNotIn("__PR_COMMENTS_DATA__", html)
        self.assertIn("Download filtered CSV", html)
        self.assertIn('id="author"', html)
        self.assertIn('id="from"', html)
        self.assertIn('id="to"', html)
        self.assertIn('"user", "bot", "deleted"', html)
        self.assertIn("ghost", html)
        self.assertNotIn("https://cdn.", html.lower())
        self.assertIn("PR created", html)
        self.assertIn("Thread", html)
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('data-theme="light"', html)
        self.assertIn("<th>PR</th><th>Comment by</th><th>Comment</th><th>Comment Kind</th><th>Comment date</th><th>Commit</th>", html)
        self.assertIn("icon-sun", html)
        self.assertIn("icon-moon", html)
        self.assertNotIn("Select a row to read the full comment", html)
        self.assertIn("detail-row", html)
        self.assertNotIn('id="detail"', html)

    def test_serve_requires_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                serve(Path(tmp))

    def test_serve_dashboard_over_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=tmp,
                transport=_fixture_transport(),
            )
            httpd = make_server(Path(tmp), host="127.0.0.1", port=0)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                port = httpd.server_address[1]
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/dashboard.html", timeout=5) as resp:
                    status = resp.status
                    body = resp.read().decode("utf-8")
                self.assertEqual(status, 200)
                self.assertIn("ghost", body)
                self.assertIn("Null check missing", body)
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
