import json
from pathlib import Path
from pathlib import PurePosixPath
import re

from openshell_lab.github_evidence import (
    build_evidence,
    extract_issue_numbers,
    select_recent_merges,
)
from openshell_lab.report import REPORT_TITLE, validate_markdown
from openshell_lab.tool_agent import MODEL_URL, build_chat_request


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
            associated_issues = ", ".join(
                f"#{issue['number']} ({issue['state']})"
                for issue in pull["associated_issues"]
            ) or "none identified"
            lines.extend(
                [
                    f"## PR #{pull['number']}: {pull['title']}",
                    f"- URL: {pull['url']}",
                    f"- Merged: {pull['merged_at']}",
                    f"- Author: {pull['author']}",
                    "- Labels: " + (", ".join(pull["labels"]) or "none"),
                    f"- Associated issues: {associated_issues}",
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
        allowed = {"accepted", "rejected"}
        if status not in allowed:
            raise AssertionError(f"unsupported report status: {status}")
        if self.context.lab_state["report_status"] != status:
            raise AssertionError(
                f"expected report status {status}, got "
                f"{self.context.lab_state['report_status']}"
            )

    def load_policy(self, policy_name):
        import yaml

        filenames = {
            "Lab 1": "lab1-github-only-baseline-filesystem.yaml",
            "GitHub-only network": "lab1-github-only-baseline-filesystem.yaml",
            "webroot-only filesystem": "lab2-webroot-only.yaml",
        }
        filename = filenames.get(policy_name)
        if filename is None:
            raise AssertionError(f"unknown policy fixture: {policy_name}")
        path = Path(__file__).parents[3] / "policies" / filename
        self.context.lab_state["policy"] = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )

    def evaluate_filesystem_write(self, path):
        policy = self.context.lab_state["policy"]["filesystem_policy"]
        candidate_path = PurePosixPath(path)
        if ".." in candidate_path.parts:
            allowed = False
        else:
            candidate = candidate_path.as_posix()
            allowed = any(
                candidate == root or candidate.startswith(root.rstrip("/") + "/")
                for root in policy.get("read_write", [])
            )
        self.context.lab_state["filesystem_action"] = (
            "allowed" if allowed else "denied"
        )

    def assert_filesystem_action(self, status):
        assert self.context.lab_state["filesystem_action"] == status

    def assert_baseline_filesystem_posture(self):
        filesystem = self.context.lab_state["policy"]["filesystem_policy"]
        assert filesystem["include_workdir"] is True
        assert "/tmp" in filesystem["read_write"]
        assert "/usr" in filesystem["read_only"]

    def _evaluate_network(self, binary, host, method):
        policy = self.context.lab_state["policy"]
        allowed = False
        for entry in policy["network_policies"].values():
            binary_match = {item["path"] for item in entry["binaries"]}
            if binary not in binary_match:
                continue
            for endpoint in entry["endpoints"]:
                if endpoint["host"] != host or endpoint["port"] != 443:
                    continue
                access = endpoint.get("access")
                if access == "read-only" and method in {"GET", "HEAD", "OPTIONS"}:
                    allowed = True
        self.context.lab_state["network_action"] = "allowed" if allowed else "denied"

    def evaluate_designated_github_read(self):
        self._evaluate_network("/usr/bin/curl", "api.github.com", "GET")

    def evaluate_network_action(self, action):
        actions = {
            "read a different host": ("/usr/bin/curl", "example.com", "GET"),
            "read GitHub with Python": ("/usr/bin/python3", "api.github.com", "GET"),
            "mutate the GitHub API": ("/usr/bin/curl", "api.github.com", "POST"),
        }
        try:
            binary, host, method = actions[action]
        except KeyError as error:
            raise AssertionError(f"unknown network action: {action}") from error
        self._evaluate_network(binary, host, method)

    def assert_network_action(self, status):
        assert self.context.lab_state["network_action"] == status

    def load_configuration(self, configuration):
        if configuration == "managed inference route":
            self.context.lab_state["configuration"] = configuration
        elif configuration == "application image metadata":
            path = Path(__file__).parents[3] / "container" / "Containerfile"
            self.context.lab_state["containerfile"] = path.read_text(encoding="utf-8")
        elif configuration == "CPU launch":
            root = Path(__file__).parents[3]
            self.context.lab_state["cpu_config"] = (
                (root / "infra/aws/lib.sh").read_text(encoding="utf-8")
                + (root / "infra/aws/launch-cpu.sh").read_text(encoding="utf-8")
            )
        elif configuration == "GPU deployment":
            root = Path(__file__).parents[3]
            paths = (
                root / "infra/aws/gpu-lib.sh",
                root / "infra/aws/start-gpu.sh",
                root / "labs/lab4/configure-vllm.sh",
                root / "labs/lab4/configure-openshell.sh",
            )
            self.context.lab_state["gpu_config"] = "\n".join(
                path.read_text(encoding="utf-8") for path in paths
            )
        else:
            raise AssertionError(f"configuration not yet implemented: {configuration}")

    def evaluate_subject(self, subject):
        if subject == "model request":
            self.context.lab_state["request"] = build_chat_request(
                [{"role": "user", "content": "report"}]
            )
        elif subject == "image identity":
            users = re.findall(
                r"^USER\s+([^\s]+)$",
                self.context.lab_state["containerfile"],
                re.MULTILINE,
            )
            assert users, "Containerfile must declare a USER directive"
            self.context.lab_state["image_user"] = users[-1]
        elif subject == "filesystem posture":
            self.context.lab_state["filesystem_evaluated"] = True
        elif subject == "CPU launch configuration":
            text = self.context.lab_state["cpu_config"]
            required = (
                "us-east-1",
                "ami-00adafae70b8029d8",
                "t3.micro",
                "rcook",
                "wide",
                "HttpTokens=required",
            )
            self.context.lab_state["cpu_settings_valid"] = all(
                item in text for item in required
            )
        elif subject == "GPU inference configuration":
            text = self.context.lab_state["gpu_config"]
            required = (
                "g6e.12xlarge",
                "Qwen/Qwen3.6-27B",
                "--dtype bfloat16",
                "--tensor-parallel-size 4",
                "--max-model-len 32768",
                "nvidia-smi",
                "-eq 4",
            )
            self.context.lab_state["gpu_settings_valid"] = all(
                item in text for item in required
            )
        elif subject == "repository safety":
            ignore = (
                Path(__file__).parents[3] / ".gitignore"
            ).read_text(encoding="utf-8").splitlines()
            self.context.lab_state["artifact_excluded"] = (
                self.context.lab_state["ignore_pattern"] in ignore
            )
        else:
            raise AssertionError(f"subject not yet implemented: {subject}")

    def assert_managed_request(self):
        request = self.context.lab_state["request"]
        forbidden_keys = {"model", "api_key", "authorization", "x-api-key"}

        def contains_forbidden_key(value):
            if isinstance(value, dict):
                return any(
                    str(key).lower() in forbidden_keys
                    or contains_forbidden_key(item)
                    for key, item in value.items()
                )
            if isinstance(value, list):
                return any(contains_forbidden_key(item) for item in value)
            return False

        if MODEL_URL != "https://inference.local/v1/chat/completions":
            raise AssertionError(f"unexpected managed inference URL: {MODEL_URL}")
        if contains_forbidden_key(request):
            raise AssertionError("managed request contains a model or credential field")

    def assert_nonroot_image(self):
        user, group = self.context.lab_state["image_user"].split(":", 1)
        assert user.isdigit() and group.isdigit()
        assert int(user) > 0 and int(group) > 0

    def load_candidate_artifact(self, artifact_type):
        patterns = {
            "environment file": ".env",
            "SSH private key": "*.key",
            "OpenShell database": "*.db",
            "TLS private key": "**/tls/",
            "model cache": ".cache/huggingface/",
        }
        try:
            self.context.lab_state["ignore_pattern"] = patterns[artifact_type]
        except KeyError as error:
            raise AssertionError(f"unknown artifact type: {artifact_type}") from error

    def assert_artifact_excluded(self):
        assert self.context.lab_state["artifact_excluded"] is True

    def assert_cpu_settings(self):
        assert self.context.lab_state["cpu_settings_valid"] is True

    def assert_gpu_settings(self):
        assert self.context.lab_state["gpu_settings_valid"] is True
