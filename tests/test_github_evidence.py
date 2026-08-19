import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from openshell_lab.github_evidence import (
    build_evidence,
    collect_evidence,
    extract_issue_numbers,
    fetch_recent_merges,
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

    def test_ignores_malformed_merge_timestamps(self):
        pulls = list(self.pulls)
        pulls.append({"number": 999, "merged_at": {"not": "a timestamp"}})
        self.assertNotIn(999, [item["number"] for item in select_recent_merges(pulls)])

    def test_orders_valid_offset_timestamps_chronologically(self):
        pulls = [
            {"number": 201, "merged_at": "2026-08-18T10:00:00-05:00"},
            {"number": 202, "merged_at": "2026-08-18T14:00:00+00:00"},
            {"number": 203, "merged_at": "2026-08-18T13:00:00Z"},
            {"number": 204, "merged_at": "2026-08-18T12:00:00Z"},
            {"number": 205, "merged_at": "2026-08-18T11:00:00Z"},
        ]
        self.assertEqual(201, select_recent_merges(pulls)[0]["number"])

    def test_extracts_only_explicit_deduplicated_issue_numbers(self):
        body = "Fixes #50, relates to #51, repeats #50, says issue 52, and names #105."
        self.assertEqual([50, 51], extract_issue_numbers(body, pr_number=105))

    def test_ignores_incidental_and_negated_issue_mentions(self):
        body = (
            "Example #40. This does not fix #41 and is not blocked by #44. "
            "Fixes NVIDIA/OpenShell#42."
        )
        self.assertEqual([42], extract_issue_numbers(body, pr_number=100))

    def test_one_relationship_keyword_can_govern_multiple_issue_references(self):
        body = "Fixes #40, #41 and #42. Related: #44. Example #43."
        self.assertEqual([40, 41, 42, 44], extract_issue_numbers(body, pr_number=100))

    def test_accepts_colons_after_every_relationship_keyword(self):
        body = "Fixes: #40. Closes: #41. Resolves: #42."
        self.assertEqual([40, 41, 42], extract_issue_numbers(body, pr_number=100))

    def test_accepts_full_github_issue_and_pull_request_urls(self):
        body = (
            "Fixes https://github.com/NVIDIA/OpenShell/issues/40 and relates to "
            "https://github.com/NVIDIA/OpenShell/pull/41."
        )
        self.assertEqual([40, 41], extract_issue_numbers(body, pr_number=100))

    def test_rejects_negated_colon_relationships(self):
        body = "This does not fix: #40 and does not close: #41."
        self.assertEqual([], extract_issue_numbers(body, pr_number=100))

    def test_rejects_numeric_prefixes_of_nonreferences(self):
        body = "Fixes #40abc and closes https://github.com/NVIDIA/OpenShell/issues/41xyz."
        self.assertEqual([], extract_issue_numbers(body, pr_number=100))

    def test_rejects_malformed_related_issue_payload(self):
        selected = select_recent_merges(self.pulls)
        malformed = dict(self.issues)
        malformed[50] = {"message": "unexpected payload"}
        with self.assertRaisesRegex(ValueError, "issue payload"):
            build_evidence(selected, malformed)

    def test_paginates_until_updated_time_proves_merge_cutoff(self):
        first_page = [
            {
                "number": number,
                "merged_at": f"2026-08-{18 if number < 6 else 17:02d}T00:00:00Z",
                "updated_at": "2026-08-19T00:00:00Z",
            }
            for number in range(1, 101)
        ]
        second_page = [
            {
                "number": 101,
                "merged_at": "2026-08-18T12:00:00Z",
                "updated_at": "2026-08-18T12:00:00Z",
            }
        ]
        with patch(
            "openshell_lab.github_evidence._curl_json",
            side_effect=[first_page, second_page],
        ) as fetch:
            selected = fetch_recent_merges("/usr/bin/curl")
        self.assertEqual(101, selected[0]["number"])
        self.assertEqual(2, fetch.call_count)

    def test_rejects_malformed_updated_time_pagination_boundary(self):
        page = [
            {
                "number": number,
                "merged_at": f"2026-08-{18 if number < 6 else 17:02d}T00:00:00Z",
                "updated_at": "2026-08-19T00:00:00Z",
            }
            for number in range(1, 101)
        ]
        page[-1]["updated_at"] = "not-a-timestamp"
        with patch("openshell_lab.github_evidence._curl_json", return_value=page):
            with self.assertRaisesRegex(ValueError, "updated-time pagination boundary"):
                fetch_recent_merges("/usr/bin/curl")

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
    if "/issues/" not in url:
        raise SystemExit("unexpected URL: " + url)
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
            self.assertEqual(5, len(calls))
            for call in calls:
                self.assertIn("--fail-with-body", call)
                self.assertIn("--max-time", call)
                self.assertIn("--max-filesize", call)
                self.assertIn("Accept: application/vnd.github+json", call)


if __name__ == "__main__":
    unittest.main()
