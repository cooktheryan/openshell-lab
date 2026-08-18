import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from openshell_lab.github_evidence import (
    build_evidence,
    collect_evidence,
    extract_issue_numbers,
    select_recent_merges,
)


FIXTURES = Path(__file__).parent / "fixtures" / "github"


class GitHubEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pulls = json.loads((FIXTURES / "pulls.json").read_text(encoding="utf-8"))
        cls.issues = {
            int(number): value
            for number, value in json.loads(
                (FIXTURES / "issues.json").read_text(encoding="utf-8")
            ).items()
        }

    def test_selects_exactly_five_latest_distinct_merges(self):
        selected = select_recent_merges(self.pulls)
        self.assertEqual([105, 103, 102, 101, 100], [item["number"] for item in selected])
        self.assertTrue(all(item["merged_at"] for item in selected))
        self.assertEqual(5, len({item["number"] for item in selected}))

    def test_requires_five_merged_pull_requests(self):
        with self.assertRaisesRegex(ValueError, "expected 5 merged pull requests"):
            select_recent_merges(self.pulls[:4])

    def test_extracts_only_explicit_deduplicated_issue_numbers(self):
        body = "Fixes #50, relates to #51, repeats #50, says issue 52, and names #105."
        self.assertEqual([50, 51], extract_issue_numbers(body, pr_number=105))

    def test_builds_bounded_relationship_evidence(self):
        selected = select_recent_merges(self.pulls)
        evidence = build_evidence(
            selected,
            self.issues,
            generated_at="2026-08-18T06:00:00Z",
        )
        first = evidence["pull_requests"][0]
        self.assertEqual([50], [item["number"] for item in first["associated_issues"]])
        self.assertEqual([51], [item["number"] for item in first["related_pull_requests"]])
        self.assertEqual(["area:gateway"], first["workstream_labels"])
        self.assertEqual("Gateway hardening", first["milestone"])
        self.assertLessEqual(len(first["body"]), 4000)

    def test_collects_evidence_with_bounded_curl_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_curl = root / "curl"
            log = root / "curl-args.jsonl"
            fake_curl.write_text(
                """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ["FAKE_CURL_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\\n")
url = args[-1]
fixtures = Path(os.environ["FAKE_GITHUB_FIXTURES"])
if "/pulls?" in url:
    sys.stdout.write((fixtures / "pulls.json").read_text(encoding="utf-8"))
else:
    number = url.rsplit("/", 1)[-1]
    issues = json.loads((fixtures / "issues.json").read_text(encoding="utf-8"))
    sys.stdout.write(json.dumps(issues[number]))
""",
                encoding="utf-8",
            )
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)
            previous = {
                key: os.environ.get(key)
                for key in ("FAKE_CURL_LOG", "FAKE_GITHUB_FIXTURES")
            }
            os.environ["FAKE_CURL_LOG"] = str(log)
            os.environ["FAKE_GITHUB_FIXTURES"] = str(FIXTURES)
            try:
                evidence = collect_evidence(
                    curl_bin=str(fake_curl),
                    generated_at="2026-08-18T06:00:00Z",
                )
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(5, len(evidence["pull_requests"]))
            self.assertGreaterEqual(len(calls), 2)
            for call in calls:
                self.assertIn("--fail-with-body", call)
                self.assertIn("--max-time", call)
                self.assertIn("--max-filesize", call)
                self.assertIn("Accept: application/vnd.github+json", call)


if __name__ == "__main__":
    unittest.main()
