import json
from pathlib import Path

from openshell_lab.github_evidence import (
    build_evidence,
    extract_issue_numbers,
    select_recent_merges,
)
from openshell_lab.report import REPORT_TITLE, validate_markdown


FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "github"


class LabChecks:
    """Thin behavior adapter over production report components."""

    def __init__(self, context):
        self.context = context

    def load_merge_evidence(self, state):
        pulls = json.loads((FIXTURES / "pulls.json").read_text(encoding="utf-8"))
        if state == "mixed merged and unmerged pull requests":
            self.context.lab_state["pulls"] = pulls
        elif state == "explicit and implicit issue candidates":
            self.context.lab_state["pulls"] = [
                {
                    "number": 105,
                    "body": "Fixes #50 and discusses issue 52 without an explicit link.",
                }
            ]
        else:
            raise AssertionError(f"unknown merge evidence fixture: {state}")

    def perform_operation(self, operation):
        pulls = self.context.lab_state["pulls"]
        if operation == "recent merge selection":
            self.context.lab_state["selected"] = select_recent_merges(pulls)
        elif operation == "issue relationship identification":
            pull = pulls[0]
            self.context.lab_state["issue_numbers"] = extract_issue_numbers(
                pull["body"], pull["number"]
            )
        else:
            raise AssertionError(f"unknown report operation: {operation}")

    def assert_five_unique_merges(self):
        selected = self.context.lab_state["selected"]
        assert len(selected) == 5
        assert len({pull["number"] for pull in selected}) == 5
        assert all(pull["merged_at"] for pull in selected)

    def assert_merge_order(self):
        selected = self.context.lab_state["selected"]
        timestamps = [pull["merged_at"] for pull in selected]
        assert timestamps == sorted(timestamps, reverse=True)

    def assert_explicit_issues(self):
        assert self.context.lab_state["issue_numbers"] == [50]

    def load_report_fixture(self, state):
        pulls = json.loads((FIXTURES / "pulls.json").read_text(encoding="utf-8"))
        issues = {
            int(number): value
            for number, value in json.loads(
                (FIXTURES / "issues.json").read_text(encoding="utf-8")
            ).items()
        }
        evidence = build_evidence(
            select_recent_merges(pulls),
            issues,
            generated_at="2026-08-18T06:00:00Z",
        )
        lines = [
            REPORT_TITLE,
            "Generated: 2026-08-18T06:00:00Z",
            "Repository: https://github.com/NVIDIA/OpenShell",
            "## Executive Summary",
            "Five evidence-grounded merge summaries.",
        ]
        for pull in evidence["pull_requests"]:
            lines.extend(
                [
                    f"## PR #{pull['number']}: {pull['title']}",
                    f"- URL: {pull['url']}",
                    f"- Merged: {pull['merged_at']}",
                    f"- Author: {pull['author']}",
                    "- Labels: " + (", ".join(pull["labels"]) or "none"),
                    "- Associated issues: none identified",
                    "### What changed",
                    "The evidence shows a focused repository change.",
                    "### Larger task context",
                    "The classification uses only collected GitHub evidence.",
                ]
            )
        markdown = "\n".join(lines) + "\n"
        if state == "missing one pull request":
            markdown = markdown.replace("## PR #100:", "## OMITTED #100:")
        elif state == "credential-bearing":
            markdown += "sk-" + "Z" * 32
        elif state != "complete":
            raise AssertionError(f"unknown report fixture: {state}")
        self.context.lab_state.update(evidence=evidence, markdown=markdown)

    def validate_report(self):
        try:
            validate_markdown(
                self.context.lab_state["markdown"],
                self.context.lab_state["evidence"],
            )
        except ValueError:
            self.context.lab_state["report_status"] = "rejected"
        else:
            self.context.lab_state["report_status"] = "accepted"

    def assert_report_status(self, status):
        assert self.context.lab_state["report_status"] == status
