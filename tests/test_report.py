import json
import errno
from pathlib import Path
import tempfile
import unittest
import stat
from unittest.mock import patch

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

    def test_normalizes_model_metadata_from_evidence(self):
        markdown = self.valid_markdown().replace(
            "- Author: alice", "- Author: fabricated"
        ).replace(
            "## PR #105: Add gateway audit event",
            "## PR #105: Fabricated title",
        )
        result = validate_markdown(markdown, self.evidence)
        self.assertIn("- Author: alice", result)
        self.assertIn("## PR #105: Add gateway audit event", result)
        self.assertNotIn("fabricated", result.lower())

    def test_rejects_embellished_report_title(self):
        markdown = self.valid_markdown().replace(
            REPORT_TITLE, REPORT_TITLE + " - unofficial", 1
        )
        with self.assertRaisesRegex(ValueError, "unexpected title"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_missing_pull_request_section(self):
        markdown = self.valid_markdown().replace("## PR #100:", "## OMITTED #100:")
        with self.assertRaisesRegex(ValueError, "(?:headings|unexpected heading)"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_empty_evidence(self):
        evidence = {"pull_requests": []}
        with self.assertRaisesRegex(ValueError, "no pull requests"):
            validate_markdown(REPORT_TITLE + "\n## Executive Summary\nNone.\n", evidence)

    def test_rejects_unterminated_fenced_code(self):
        markdown = self.valid_markdown().replace(
            "## PR #105:", "```text\n## PR #105:", 1
        )
        with self.assertRaisesRegex(ValueError, "unterminated"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_pull_request_headings_inside_balanced_fences(self):
        markdown = self.valid_markdown()
        first = markdown.index("## PR #105:")
        markdown = markdown[:first] + "```markdown\n" + markdown[first:] + "```\n"
        with self.assertRaisesRegex(ValueError, "headings|fenced code blocks"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_unapproved_top_level_sections(self):
        markdown = self.valid_markdown() + "\n## Appendix\nUntrusted model prose.\n"
        with self.assertRaisesRegex(ValueError, "unexpected heading"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_duplicate_contract_headings(self):
        markdown = self.valid_markdown().replace(
            "## Executive Summary\n",
            "## Executive Summary\nFirst.\n## Executive Summary\n",
            1,
        )
        with self.assertRaisesRegex(ValueError, "exactly one executive summary"):
            validate_markdown(markdown, self.evidence)

    def test_rejects_deep_or_duplicate_metadata_structure(self):
        deep = self.valid_markdown() + "\n#### Unapproved detail\n"
        duplicate = self.valid_markdown().replace(
            "- Author: alice",
            "- Author: alice\n- Author: contradictory",
            1,
        )
        for markdown in (deep, duplicate):
            with self.subTest(markdown=markdown[-80:]):
                with self.assertRaisesRegex(ValueError, "unexpected heading|duplicate"):
                    validate_markdown(markdown, self.evidence)

    def test_heading_names_may_be_mentioned_in_prose(self):
        markdown = self.valid_markdown().replace(
            "The evidence shows a focused repository change.",
            "The phrase ### What changed is part of this evidence summary.",
            1,
        )
        self.assertTrue(validate_markdown(markdown, self.evidence).startswith(REPORT_TITLE))

    def test_rejects_credential_material(self):
        credentials = (
            "sk-" + "Z" * 32,
            "ghp_" + "A" * 36,
            "github_pat_" + "A" * 40,
        )
        for credential in credentials:
            with self.subTest(credential=credential[:12]):
                with self.assertRaisesRegex(ValueError, "credential"):
                    validate_markdown(self.valid_markdown() + credential, self.evidence)

    def test_required_fields_must_be_structural_lines(self):
        markdown = self.valid_markdown().replace(
            "- URL: https://github.com/NVIDIA/OpenShell/pull/105",
            "Prose mentioning - URL: https://github.com/NVIDIA/OpenShell/pull/105",
        )
        with self.assertRaisesRegex(ValueError, "required structure"):
            validate_markdown(markdown, self.evidence)

    def test_evidence_index_is_deterministic(self):
        index = render_evidence_index(self.evidence)
        self.assertIn("## Evidence Index", index)
        self.assertEqual(5, index.count("\n| [#"))
        self.assertIn("[#50](https://github.com/NVIDIA/OpenShell/issues/50)", index)

    def test_evidence_index_escapes_untrusted_table_cells(self):
        evidence = json.loads(json.dumps(self.evidence))
        evidence["pull_requests"][0]["labels"] = ["area:one|two\nthree"]
        evidence["pull_requests"][0]["milestone"] = "line one|line two\nline three"
        index = render_evidence_index(evidence)
        self.assertIn(r"area:one\|two three", index)
        self.assertIn(r"line one\|line two line three", index)

    def test_evidence_metadata_is_credential_scanned(self):
        evidence = json.loads(json.dumps(self.evidence))
        evidence["pull_requests"][0]["labels"] = ["ghp_" + "A" * 36]
        with self.assertRaisesRegex(ValueError, "credential"):
            validate_markdown(self.valid_markdown(), evidence)

    def test_atomic_writer_leaves_only_final_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            write_report(report, self.valid_markdown())
            self.assertEqual(self.valid_markdown(), report.read_text(encoding="utf-8"))
            self.assertEqual([report], list(Path(directory).iterdir()))
            self.assertEqual(0o600, stat.S_IMODE(report.stat().st_mode))

    def test_unexpected_directory_fsync_error_is_reported(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "openshell_lab.report.os.fsync",
            side_effect=[None, OSError(errno.EIO, "durability failure")],
        ):
            with self.assertRaisesRegex(OSError, "durability failure"):
                write_report(Path(directory) / "report.md", "content")

    def test_windows_skips_unsupported_directory_fsync_after_publication(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "openshell_lab.report.DIRECTORY_FSYNC_SUPPORTED", False
        ):
            report = Path(directory) / "report.md"
            write_report(report, "content")
            self.assertEqual("content", report.read_text(encoding="utf-8"))

    def test_cleanup_failure_does_not_mask_original_write_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "openshell_lab.report.os.chmod", side_effect=PermissionError("original")
        ), patch("openshell_lab.report.os.unlink", side_effect=OSError("cleanup")):
            with self.assertRaisesRegex(PermissionError, "original"):
                write_report(Path(directory) / "report.md", "content")


if __name__ == "__main__":
    unittest.main()
