from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comment_intel.adapters.github import records_from_pr_bundle
from comment_intel.adapters.gitlab import records_from_discussions
from comment_intel.adapters.local_json import records_from_dump
from comment_intel.checkpoint import load_cutoff, parse_report_markers, write_checkpoint
from comment_intel.classify import classify_comment
from comment_intel.detect import parse_remote_url, provider_from_host, resolve_base_branch, RepoIdentity
from comment_intel.generate import merge_patterns_markdown, preserve_user_customizations
from comment_intel.normalize import make_record, normalize_body
from comment_intel.pipeline import orchestrate
from comment_intel.proc import parse_cli_json
from comment_intel.refine import merge_uniques
from comment_intel.report import render_report
from comment_intel.timeutil import is_after

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class DetectTests(unittest.TestCase):
    def test_parse_github_ssh(self):
        provider, host, owner, repo = parse_remote_url("git@github.com:framedparadox/pr-comments.git")
        self.assertEqual((provider, host, owner, repo), ("github", "github.com", "framedparadox", "pr-comments"))

    def test_parse_https_with_token(self):
        url = "https://x-access-token:ghs_secret@github.com/acme/app.git"
        provider, host, owner, repo = parse_remote_url(url)
        self.assertEqual((provider, host, owner, repo), ("github", "github.com", "acme", "app"))

    def test_parse_gitlab_nested(self):
        provider, host, owner, repo = parse_remote_url("https://gitlab.com/group/sub/app.git")
        self.assertEqual(provider, "gitlab")
        self.assertEqual(owner, "group/sub")
        self.assertEqual(repo, "app")

    def test_provider_gitea(self):
        self.assertEqual(provider_from_host("codeberg.org"), "gitea")
        self.assertEqual(provider_from_host("bitbucket.org"), "bitbucket")

    def test_ambiguous_base_branch_errors(self):
        ident = RepoIdentity(
            git_root=Path("."),
            provider="github",
            host="github.com",
            owner="a",
            repo="b",
            remote_url=None,
        )

        def runner(args, cwd=None):
            return subprocess.CompletedProcess(args, 1, "", "")

        with self.assertRaises(SystemExit):
            resolve_base_branch(ident, requested=None, runner=runner, api_default=None)


class NormalizeTests(unittest.TestCase):
    def test_strips_markdown_and_case(self):
        body = "See [docs](http://x) and `User.Roles` **please**"
        self.assertEqual(normalize_body(body), "see docs and user.roles please")

    def test_identical_bot_text_same_key(self):
        a = make_record(
            provider="github",
            host="github.com",
            repo="acme/app",
            pr_number=1,
            pr_title="a",
            kind="issue_comment",
            comment_id=1,
            author="bot",
            author_type="bot",
            created_at="2026-01-01T00:00:00Z",
            body="Rebase this PR\n",
        )
        b = make_record(
            provider="github",
            host="github.com",
            repo="acme/app",
            pr_number=2,
            pr_title="b",
            kind="issue_comment",
            comment_id=2,
            author="bot",
            author_type="bot",
            created_at="2026-01-02T00:00:00Z",
            body="rebase this pr",
        )
        from comment_intel.normalize import dedup_key

        self.assertEqual(dedup_key(a["repo"], a["body_normalized"]), dedup_key(b["repo"], b["body_normalized"]))


class ClassifyTests(unittest.TestCase):
    def test_conventional_blocking_issue(self):
        labels = classify_comment({"body": "issue (blocking): authz must be enforced", "body_normalized": "issue (blocking): authz must be enforced"})
        self.assertEqual(labels["priority"], "P1")
        self.assertIn("issue", labels["tags"])
        self.assertIn("blocking", labels["tags"])

    def test_null_check_correctness(self):
        labels = classify_comment(
            {
                "body": "Null check missing before user.roles access; will 500 on anonymous requests.",
                "body_normalized": "null check missing before user.roles access; will 500 on anonymous requests.",
            }
        )
        self.assertEqual(labels["category"], "correctness")
        self.assertEqual(labels["priority"], "P1")
        self.assertTrue(labels["actionable"])

    def test_nit_style(self):
        labels = classify_comment({"body": "nit: rename to userCount", "body_normalized": "nit: rename to usercount"})
        self.assertEqual(labels["category"], "style")
        self.assertEqual(labels["priority"], "P3")

    def test_praise_not_actionable(self):
        labels = classify_comment({"body": "praise: nice tests", "body_normalized": "praise: nice tests"})
        self.assertFalse(labels["actionable"])
        self.assertIn("praise", labels["tags"])

    def test_bot_workflow(self):
        labels = classify_comment(
            {
                "body": "Dependabot is rebasing this PR because the target branch was updated.",
                "body_normalized": "dependabot is rebasing this pr because the target branch was updated.",
                "author_type": "bot",
            }
        )
        self.assertEqual(labels["category"], "workflow")
        self.assertIn("bot", labels["tags"])


class AdapterTests(unittest.TestCase):
    def test_github_bundle(self):
        from comment_intel.adapters import PullRequest

        pr = PullRequest(
            number=150,
            title="Harden session lookup",
            state="open",
            url="https://github.com/acme/app/pull/150",
            created_at="2026-08-01T00:00:00Z",
            updated_at="2026-08-12T00:00:00Z",
        )
        records = records_from_pr_bundle(
            "github.com",
            "acme/app",
            pr,
            _load("github_issue_comments.json"),
            _load("github_review_comments.json"),
            _load("github_reviews.json"),
        )
        kinds = {r["kind"] for r in records}
        self.assertIn("issue_comment", kinds)
        self.assertIn("review_comment", kinds)
        self.assertIn("review_summary", kinds)
        ghost = next(r for r in records if r["id"].endswith(":9933"))
        self.assertEqual(ghost["author_type"], "deleted")
        self.assertEqual(ghost["author"], "ghost")
        inline = next(r for r in records if r["kind"] == "review_comment" and r["path"] == "auth.py")
        self.assertEqual(inline["line"], 112)
        # empty review body dropped
        self.assertFalse(any(r["id"].endswith(":9002") for r in records))

    def test_gitlab_skips_system_notes(self):
        from comment_intel.adapters import PullRequest

        pr = PullRequest(number=9, title="List", state="merged", url="https://gitlab.com/acme/app/-/merge_requests/9", created_at=None, updated_at=None)
        records = records_from_discussions("gitlab.com", "acme/app", pr, _load("gitlab_discussions.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kind"], "diff_note")
        self.assertEqual(records[0]["path"], "api/list.rb")
        self.assertEqual(records[0]["line"], 44)

    def test_cutoff_filters_old_github_rows(self):
        from comment_intel.adapters import PullRequest

        pr = PullRequest(number=150, title="x", state="open", url=None, created_at=None, updated_at=None)
        records = records_from_pr_bundle("github.com", "acme/app", pr, _load("github_issue_comments.json"), [], [])
        recent = [r for r in records if is_after(r["created_at"], "2026-08-10T00:00:00Z")]
        self.assertTrue(all(r["created_at"] > "2026-08-10" for r in recent))
        self.assertEqual(len(recent), 2)

    def test_local_dump_passthrough(self):
        payload = [
            {
                "id": "local:acme/app:pr:1:note:1",
                "provider": "local",
                "host": "example.com",
                "repo": "acme/app",
                "pr_number": 1,
                "kind": "note",
                "created_at": "2026-01-01T00:00:00Z",
                "body": "Please add tests for the parser.",
            }
        ]
        records = records_from_dump("example.com", "acme/app", payload)
        self.assertEqual(len(records), 1)
        self.assertIn("tests", records[0]["body_normalized"])


class DedupTests(unittest.TestCase):
    def test_merges_same_body(self):
        comments = [
            make_record(
                provider="github", host="github.com", repo="acme/app", pr_number=1, pr_title="a",
                kind="issue_comment", comment_id=1, author="bot", author_type="bot",
                created_at="2026-01-01T00:00:00Z", body="Rebase this PR",
            ),
            make_record(
                provider="github", host="github.com", repo="acme/app", pr_number=2, pr_title="b",
                kind="issue_comment", comment_id=2, author="bot", author_type="bot",
                created_at="2026-01-02T00:00:00Z", body="rebase this pr",
            ),
        ]
        uniques, _ = merge_uniques([], comments)
        self.assertEqual(len(uniques), 1)
        self.assertEqual(uniques[0]["seen_count"], 2)
        self.assertEqual({o["pr_number"] for o in uniques[0]["occurrences"]}, {1, 2})

    def test_does_not_reclassify_existing(self):
        comments = [
            make_record(
                provider="github", host="github.com", repo="acme/app", pr_number=1, pr_title="a",
                kind="issue_comment", comment_id=1, author="a", author_type="user",
                created_at="2026-01-01T00:00:00Z", body="nit: rename to userCount",
            )
        ]
        uniques, _ = merge_uniques([], comments)
        uniques[0]["category"] = "documentation"
        uniques[0]["priority"] = "P0"
        again, _ = merge_uniques(uniques, comments)
        self.assertEqual(again[0]["category"], "documentation")
        self.assertEqual(again[0]["priority"], "P0")
        self.assertEqual(again[0]["seen_count"], 1)


class ReportCheckpointTests(unittest.TestCase):
    def test_prepends_run_and_keeps_old(self):
        comments = [
            make_record(
                provider="github", host="github.com", repo="acme/app", pr_number=8, pr_title="Old",
                kind="issue_comment", comment_id=1, author="a", author_type="user",
                created_at="2026-01-01T00:00:00Z", body="old comment about tests missing",
            )
        ]
        uniques, _ = merge_uniques([], comments)
        first = render_report(
            host="github.com",
            repo="acme/app",
            base_branch="main",
            cutoff="2026-01-01T00:00:00Z",
            last_pr=8,
            comments=comments,
            uniques=uniques,
            new_uniques=uniques,
            previous_markdown="",
            run_at="2026-01-02T00:00:00Z",
        )
        newer = [
            make_record(
                provider="github", host="github.com", repo="acme/app", pr_number=9, pr_title="New",
                kind="issue_comment", comment_id=2, author="b", author_type="user",
                created_at="2026-02-01T00:00:00Z", body="XSS in the search box",
            )
        ]
        all_comments = comments + newer
        all_uniques, new_u = merge_uniques(uniques, newer)
        second = render_report(
            host="github.com",
            repo="acme/app",
            base_branch="main",
            cutoff="2026-02-01T00:00:00Z",
            last_pr=9,
            comments=all_comments,
            uniques=all_uniques,
            new_uniques=new_u,
            previous_markdown=first + "\n## User customizations\n\nKeep me.\n",
            run_at="2026-02-02T00:00:00Z",
        )
        self.assertIn("<!-- comment-intel:cutoff:2026-02-01T00:00:00Z -->", second)
        self.assertLess(second.find("## Run: 2026-02-02T00:00:00Z"), second.find("## Run: 2026-01-02T00:00:00Z"))
        self.assertIn("Keep me.", second)
        markers = parse_report_markers(second)
        self.assertEqual(markers["cutoff"], "2026-02-01T00:00:00Z")
        self.assertEqual(markers["base_branch"], "main")

    def test_checkpoint_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            write_checkpoint(path, {"cutoff": "2026-08-15T14:32:00Z", "repo": "acme/app"})
            report = Path(tmp) / "REPORT.md"
            report.write_text("<!-- comment-intel:cutoff:2026-01-01T00:00:00Z -->\n", encoding="utf-8")
            self.assertEqual(load_cutoff(Path(tmp)), "2026-08-15T14:32:00Z")


class GenerateMergeTests(unittest.TestCase):
    def test_preserves_user_customizations_and_merges_ids(self):
        existing = """# Pattern library

## Patterns

<!-- comment-intel:pattern:correctness:logic-bug -->
### correctness: logic-bug
- **Category:** correctness
- **Priority:** P1
- **Actionable:** yes
- **Rule:** Guard nulls.
- **Anti-pattern:** Nested access
- **Examples:**
  - old
- **Provenance:** seed
- **Confirmed in:** #1
- **Seen:** 1

## User customizations

Do not delete this note.
"""
        uniques = [
            {
                "category": "correctness",
                "subcategory": "logic-bug",
                "priority": "P1",
                "actionable": True,
                "body": "Null check missing before user.roles",
                "seen_count": 2,
                "occurrences": [{"pr_number": 150}, {"pr_number": 162}],
                "provenance": {"host": "github.com", "repo": "acme/app"},
            }
        ]
        merged, changed = merge_patterns_markdown(existing, uniques)
        self.assertGreaterEqual(changed, 1)
        self.assertIn("Do not delete this note.", merged)
        self.assertIn("#150", merged)
        self.assertIn("#162", merged)
        self.assertIn("#1", merged)
        preserved = preserve_user_customizations(existing, "# Pattern library\n\n## User customizations\n\nwiped\n")
        self.assertIn("Do not delete this note.", preserved)
        self.assertNotIn("wiped", preserved)


class SkillLayoutTests(unittest.TestCase):
    def test_package_has_no_per_agent_skill_trees(self):
        for name in (".claude", ".agents", ".github"):
            self.assertFalse((ROOT / name / "skills").exists(), name)


class ProcTests(unittest.TestCase):
    def test_concatenated_json_arrays(self):
        data = parse_cli_json('[{"id":1}][{"id":2}]')
        self.assertEqual([row["id"] for row in data], [1, 2])


class SkillFrontmatterTests(unittest.TestCase):
    REQUIRED = {
        "ingest-comments",
        "refine-comments",
        "generate-skills",
        "orchestrate-repo-comment-intelligence",
        "code-review",
        "git-checkin",
        "commit-hooks",
    }

    def test_frontmatter_name_matches_directory(self):
        skills = ROOT / "skills"
        found = set()
        for skill_md in skills.glob("*/SKILL.md"):
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), skill_md)
            block = text.split("---", 2)[1]
            name = None
            description = None
            for line in block.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
            self.assertEqual(name, skill_md.parent.name)
            self.assertTrue(description)
            self.assertLessEqual(len(description), 1024)
            self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
            found.add(name)
        self.assertTrue(self.REQUIRED <= found)


class PipelineLocalJsonTests(unittest.TestCase):
    def test_orchestrate_is_idempotent(self):
        env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, env=env)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/acme/app.git"],
                cwd=root,
                check=True,
                capture_output=True,
                env=env,
            )
            shutil.copytree(ROOT / "skills", root / "skills")
            dump = [
                {
                    "id": "github:acme/app:pr:3:issue_comment:1",
                    "provider": "github",
                    "host": "github.com",
                    "repo": "acme/app",
                    "pr_number": 3,
                    "pr_title": "Parser",
                    "kind": "issue_comment",
                    "author": "ada",
                    "author_type": "user",
                    "created_at": "2026-03-01T00:00:00Z",
                    "body": "Please add tests for the parser.",
                    "path": "parser.py",
                    "line": 10,
                    "url": "https://github.com/acme/app/pull/3#issuecomment-1",
                },
                {
                    "id": "github:acme/app:pr:3:review_comment:2",
                    "provider": "github",
                    "host": "github.com",
                    "repo": "acme/app",
                    "pr_number": 3,
                    "kind": "review_comment",
                    "author": "ada",
                    "author_type": "user",
                    "created_at": "2026-03-01T01:00:00Z",
                    "body": "Null check missing before `user.roles` access; will 500.",
                    "path": "auth.py",
                    "line": 4,
                },
            ]
            dump_path = root / "dump.json"
            dump_path.write_text(json.dumps(dump), encoding="utf-8")
            first = orchestrate(
                git_dir=root,
                base_branch="main",
                local_json=dump_path,
            )
            self.assertEqual(first["new_comments"], 2)
            self.assertEqual(first["total_comments"], 2)
            self.assertGreaterEqual(first["unique_comments"], 2)
            self.assertFalse((root / ".claude").exists())
            self.assertFalse((root / ".agents").exists())
            self.assertFalse((root / ".github").exists())
            report = Path(first["artifact_dir"]) / "REPORT.md"
            self.assertTrue(report.is_file())
            self.assertIn("comment-intel:cutoff:", report.read_text(encoding="utf-8"))
            patterns = (root / "skills" / "code-review" / "references" / "patterns.md").read_text(encoding="utf-8")
            self.assertIn("## User customizations", patterns)
            second = orchestrate(
                git_dir=root,
                base_branch="main",
                local_json=dump_path,
            )
            self.assertEqual(second["new_comments"], 0)
            self.assertEqual(second["total_comments"], 2)
            ledger = (Path(first["artifact_dir"]) / "comments.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(ledger), 2)


if __name__ == "__main__":
    unittest.main()
