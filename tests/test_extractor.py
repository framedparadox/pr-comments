from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pr_comments.cli import main
from pr_comments.detect import parse_remote_url, parse_repo_slug, provider_from_host
from pr_comments.export import csv_safe, write_csv
from pr_comments.extract import extract
from pr_comments.github import (
    records_from_issue_comments,
    records_from_review_comments,
    records_from_reviews,
    pull_request_from_api,
)
from pr_comments.normalize import author_type_from, number_from_url
from pr_comments.schema import CSV_FIELDS

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _prs():
    return {item["number"]: pull_request_from_api(item) for item in _load("github_pulls.json")}


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
        pulls = _load("github_pulls.json")
        issues = _load("github_issue_comments.json")
        reviews_c = _load("github_review_comments.json")
        reviews = _load("github_reviews.json")

        def transport(path: str):
            base = path.split("?", 1)[0]
            if base.endswith("/acme/app") and "/pulls" not in base and "/issues" not in base:
                return _load("github_repo.json")
            if "/pulls/" in base and base.endswith("/reviews"):
                number = int(base.rsplit("/", 2)[1])
                return [r for r in reviews if (number == 150 and r["id"] in {9001, 9002}) or (number == 148 and r["id"] == 8800)]
            if base.endswith("/pulls/comments"):
                return reviews_c
            if base.endswith("/issues/comments"):
                return issues
            if base.endswith("/pulls"):
                return pulls
            raise AssertionError(path)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "export"
            result = extract(
                repo="acme/app",
                host="github.com",
                base_branch="main",
                output_dir=out,
                transport=transport,
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
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("ghost", html)
            self.assertIn("Null check missing", html)
            self.assertIn("aaa111b", html)

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


if __name__ == "__main__":
    unittest.main()
