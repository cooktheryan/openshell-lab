import json
from pathlib import Path
import tempfile
import unittest

from openshell_lab.github_evidence import build_evidence, select_recent_merges
from openshell_lab.report import REPORT_TITLE, render_evidence_index, validate_markdown, write_report


FIXTURES = Path(__file__).parent / "fixtures" / "github"


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pulls = json.loads((FIXTURES / "pulls.json").read_text(encoding="utf-8"))
        issues = {
            int(number): value
            for number, value in json.loads(
                (FIXTURES / "issues.json").read_text(encoding="utf-8")
            ).items()
        }
        cls.evidence = build_evidence(
            select_recent_merges(pulls),
            issues,
            generated_at="2026-08-18T06:00:00Z",
        )

    def valid_markdown(self):
        lines = [
            REPORT_TITLE,
            "Generated: 2026-08-18T06:00:00Z",
            "Repository: https://github.com/NVIDIA/OpenShell",
            "## Executive Summary",
            "These five merges improve gateway, policy, documentation, supervisor, and CLI behavior.",
        ]
        for pull in self.evidence["pull_requests"]:
            lines.extend(
                [
                    f"## PR #{pull['number']}: {pull['title']}",
                    f"- URL: {pull['url']}",
                    f"- Merged: {pull['merged_at']}",
                    f"- Author: {pull['author']}",
                    "- Labels: " + (", ".join(pull["labels"]) or "none"),
                    "- Associated issues: "
                    + (", ".join(str(item["number"]) for item in pull["associated_issues"]) or "none identified"),
                    "### What changed",
                    "The evidence shows a focused repository change.",
                    "### Larger task context",
                    "The classification is based only on issue, label, milestone, or body evidence.",
                ]
            )
        return "\n".join(lines) + "\n"

    def test_accepts_complete_five_pull_request_report(self):
        result = validate_markdown(self.valid_markdown(), self.evidence)
        self.assertTrue(result.startswith(REPORT_TITLE))

    def test_rejects_missing_pull_request_section(self):
        markdown = self.valid_markdown().replace("## PR #100:", "## OMITTED #100:")
        with self.assertRaisesRegex(ValueError, "headings"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_credential_material(self):
        credential = "sk-" + "Z" * 32
        with self.assertRaisesRegex(ValueError, "credential"):
            validate_markdown(self.valid_markdown() + credential, self.evidence)

    def test_evidence_index_is_deterministic(self):
        index = render_evidence_index(self.evidence)
        self.assertIn("## Evidence Index", index)
        self.assertEqual(5, index.count("\n| [#"))
        self.assertIn("[#50](https://github.com/NVIDIA/OpenShell/issues/50)", index)

    def test_atomic_writer_leaves_only_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            write_report(report, self.valid_markdown())
            self.assertEqual(self.valid_markdown(), report.read_text(encoding="utf-8"))
            self.assertEqual([report], list(Path(directory).iterdir()))


if __name__ == "__main__":
    unittest.main()
