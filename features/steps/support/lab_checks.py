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
from openshell_lab.tool_agent import (
    MODEL_URL,
    build_chat_request,
    recoverable_tool_error,
)
from test_support.shell_lab_harness import (
    run_gpu_profile_detector,
    run_cpu_lab_sequence,
    run_forwarded_launcher,
    run_lab4_launcher,
    run_secret_scan_with_failing_search,
    run_secret_scan_without_rg,
)


FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "github"


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _contains_credential_or_model(value):
    forbidden_keys = {
        "model",
        "apikey",
        "authorization",
        "xapikey",
        "token",
        "accesstoken",
        "bearertoken",
    }
    if isinstance(value, dict):
        return any(
            re.sub(r"[^a-z0-9]", "", str(key).lower()) in forbidden_keys
            or _contains_credential_or_model(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_credential_or_model(item) for item in value)
    if isinstance(value, str):
        credential_patterns = (
            r"\b(?:Bearer|Basic)\s+\S+",
            r"sk-[A-Za-z0-9_-]{20,}",
            r"AKIA[0-9A-Z]{16}",
            r"gh[opusr]_[A-Za-z0-9_]{20,}",
            r"github_pat_[A-Za-z0-9_]{20,}",
            r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
        )
        return any(re.search(pattern, value, re.I) for pattern in credential_patterns)
    return False


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
        _require(len(selected) == 5, "expected exactly five merges")
        _require(
            len({pull["number"] for pull in selected}) == 5,
            "expected five unique merges",
        )
        _require(all(pull["merged_at"] for pull in selected), "merge timestamp missing")

    def assert_merge_order(self):
        selected = self.context.lab_state["selected"]
        timestamps = [pull["merged_at"] for pull in selected]
        _require(
            timestamps == sorted(timestamps, reverse=True),
            "merges are not newest first",
        )

    def assert_explicit_issues(self):
        _require(
            self.context.lab_state["issue_numbers"] == [50],
            "unexpected issue relationship set",
        )

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

    def load_streamlit_prompt(self, state):
        prompts = {
            "empty": "",
            "over 4000 characters": "x" * 4001,
        }
        try:
            self.context.lab_state["streamlit_prompt"] = prompts[state]
        except KeyError as error:
            raise AssertionError(f"unknown Streamlit prompt state: {state}") from error

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
            "Lab 4": "lab4-streamlit.yaml",
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
                candidate == root
                or (
                    not root.startswith("/dev/")
                    and candidate.startswith(root.rstrip("/") + "/")
                )
                for root in policy.get("read_write", [])
            )
        self.context.lab_state["filesystem_action"] = (
            "allowed" if allowed else "denied"
        )

    def assert_filesystem_action(self, status):
        _require(status in {"allowed", "denied"}, f"unsupported status: {status}")
        _require(
            self.context.lab_state["filesystem_action"] == status,
            f"expected filesystem action {status}",
        )

    def assert_baseline_filesystem_posture(self):
        filesystem = self.context.lab_state["policy"]["filesystem_policy"]
        _require(filesystem["include_workdir"] is True, "workdir must be included")
        _require("/tmp" in filesystem["read_write"], "/tmp must be writable")
        _require("/usr" in filesystem["read_only"], "/usr must be read-only")

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
        _require(status in {"allowed", "denied"}, f"unsupported status: {status}")
        _require(
            self.context.lab_state["network_action"] == status,
            f"expected network action {status}",
        )

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
                root / "labs/lab5/detect-gpu-profile.sh",
                root / "labs/lab5/configure-vllm.sh",
                root / "labs/lab5/configure-openshell.sh",
            )
            self.context.lab_state["gpu_config"] = "\n".join(
                path.read_text(encoding="utf-8") for path in paths
            )
        elif configuration == "OpenShell release installation":
            path = Path(__file__).parents[3] / "infra/remote/bootstrap-rhel10.sh"
            self.context.lab_state["bootstrap_config"] = path.read_text(
                encoding="utf-8"
            )
        elif configuration == "sandbox launchers":
            root = Path(__file__).parents[3]
            self.context.lab_state["sandbox_launchers"] = {
                lab: (root / "labs" / lab / "run.sh").read_text(encoding="utf-8")
                for lab in ("lab1", "lab2", "lab3", "lab4", "lab5")
            }
        elif configuration == "Lab 5 launcher":
            path = Path(__file__).parents[3] / "labs" / "lab5" / "run.sh"
            self.context.lab_state["lab5_launcher"] = path.read_text(
                encoding="utf-8"
            )
        elif configuration == "Lab 1 launcher":
            path = Path(__file__).parents[3] / "labs" / "lab1" / "run.sh"
            self.context.lab_state["lab1_launcher"] = path.read_text(
                encoding="utf-8"
            )
        elif configuration == "Lab 3 launcher":
            self.context.lab_state["repository_root"] = Path(__file__).parents[3]
        elif configuration == "forwarded sandbox launchers":
            self.context.lab_state["repository_root"] = Path(__file__).parents[3]
        elif configuration == "CPU lab sequence":
            self.context.lab_state["cpu_sequence_path"] = (
                Path(__file__).parents[3] / "infra" / "remote" / "run-cpu-labs.sh"
            )
        elif configuration == "home runner installer":
            self.context.lab_state["home_runner_installer"] = (
                Path(__file__).parents[3] / "infra" / "remote" / "install-runner.sh"
            ).read_text(encoding="utf-8")
        elif configuration == "secret scanner without ripgrep":
            self.context.lab_state["secret_scanner_path"] = (
                Path(__file__).parents[3] / "scripts" / "scan-secrets.sh"
            )
        elif configuration == "invalid evidence tool call":
            self.context.lab_state["tool_error"] = ValueError(
                "issue is not explicitly referenced by a selected pull request"
            )
        elif configuration == "failing secret search tool":
            self.context.lab_state["secret_scanner_path"] = (
                Path(__file__).parents[3] / "scripts" / "scan-secrets.sh"
            )
        elif configuration == "Lab 4 managed inference":
            self.context.lab_state["configuration"] = configuration
        elif configuration == "Streamlit image metadata":
            path = Path(__file__).parents[3] / "labs" / "lab4" / "Containerfile"
            self.context.lab_state["containerfile"] = path.read_text(
                encoding="utf-8"
            )
        elif configuration == "Lab 4 launcher":
            path = Path(__file__).parents[3] / "labs" / "lab4" / "run.sh"
            self.context.lab_state["lab4_launcher"] = path.read_text(
                encoding="utf-8"
            )
        elif configuration == "Lab 4 verifier":
            path = Path(__file__).parents[3] / "labs" / "lab4" / "verify.sh"
            self.context.lab_state["lab4_verifier"] = path.read_text(
                encoding="utf-8"
            )
        elif configuration == "Lab 4 evidence collector":
            path = Path(__file__).parents[3] / "scripts" / "collect-evidence.sh"
            self.context.lab_state["lab4_collector"] = path.read_text(
                encoding="utf-8"
            )
        else:
            raise AssertionError(f"configuration not yet implemented: {configuration}")

    def load_gpu_topology(self, topology):
        topologies = {
            "four NVIDIA L4 GPUs": ("NVIDIA L4",) * 4,
            "four NVIDIA L40S GPUs": ("NVIDIA L40S",) * 4,
            "three NVIDIA L4 GPUs": ("NVIDIA L4",) * 3,
            "mixed NVIDIA GPUs": (
                "NVIDIA L4",
                "NVIDIA L4",
                "NVIDIA L40S",
                "NVIDIA L40S",
            ),
            "four NVIDIA RTX PRO GPUs": (
                "NVIDIA RTX PRO 6000 Blackwell Server Edition",
            )
            * 4,
        }
        try:
            self.context.lab_state["gpu_names"] = topologies[topology]
        except KeyError as error:
            raise AssertionError(f"unknown GPU topology: {topology}") from error

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
            _require(users, "Containerfile must declare a USER directive")
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
        elif subject == "CPU launch safety":
            text = self.context.lab_state["cpu_config"]
            lock_position = text.find('launch_lock="${STATE_FILE}.launch.lock"')
            state_position = text.find(
                'write_cpu_state "$instance_id" "$subnet_id" '
                '"$security_group_id" provisional'
            )
            wait_position = text.find("ec2 wait instance-running")
            self.context.lab_state["cpu_launch_safety_valid"] = (
                lock_position >= 0
                and state_position >= 0
                and wait_position >= 0
                and state_position < wait_position
            )
        elif subject == "GPU inference configuration":
            text = self.context.lab_state["gpu_config"]
            required = (
                "g6.12xlarge",
                "Qwen/Qwen3.6-27B",
                "--dtype bfloat16",
                "--tensor-parallel-size 4",
                "--max-model-len 32768",
                "--max-num-seqs $MAX_NUM_SEQS",
                "nvidia-ctk cdi generate",
                "g6-l4 16",
                "g6e-l40s 256",
            )
            self.context.lab_state["gpu_settings_valid"] = all(
                item in text for item in required
            )
        elif subject == "GPU profile selection":
            root = Path(__file__).parents[3]
            self.context.lab_state["gpu_profile_result"] = (
                run_gpu_profile_detector(
                    root / "labs" / "lab5" / "detect-gpu-profile.sh",
                    self.context.lab_state["gpu_names"],
                )
            )
        elif subject == "OpenShell release selection":
            text = self.context.lab_state["bootstrap_config"]
            required = (
                "https://github.com/NVIDIA/OpenShell/releases/latest",
                'OPENSHELL_VERSION="${latest_tag}" sh',
                'installed_tag="v${installed_version#openshell }"',
                '[[ "$installed_tag" != "$latest_tag" ]]',
            )
            self.context.lab_state["openshell_release_valid"] = all(
                item in text for item in required
            )
        elif subject == "canonical sandbox process configuration":
            launchers = self.context.lab_state["sandbox_launchers"]
            self.context.lab_state["durable_canonical_processes"] = {
                lab: "-- /usr/bin/sleep infinity" in text and "-- /bin/true" not in text
                for lab, text in launchers.items()
            }
        elif subject == "loopback forward cleanup":
            text = self.context.lab_state["lab5_launcher"]
            self.context.lab_state["lab5_forward_cleanup_valid"] = (
                'openshell forward stop 18080 "$SANDBOX"' in text
                and "openshell forward stop 18080 openshell-lab3" not in text
            )
        elif subject == "source upload ordering":
            text = self.context.lab_state["lab1_launcher"]
            create_position = text.find("openshell sandbox create")
            upload_position = text.find("openshell sandbox upload")
            exec_position = text.find("openshell sandbox exec")
            upload_line = next(
                (
                    line
                    for line in text.splitlines()
                    if line.startswith("openshell sandbox upload ")
                ),
                "",
            )
            self.context.lab_state["lab1_upload_ordering_valid"] = (
                '--upload "$ROOT/src:/sandbox"' not in text
                and upload_position >= 0
                and create_position < upload_position < exec_position
                and upload_line
                == 'openshell sandbox upload "$SANDBOX" "$ROOT/src" /sandbox >/dev/null'
            )
        elif subject == "non-interactive forward lifecycle":
            root = self.context.lab_state["repository_root"]
            self.context.lab_state["forwarded_launcher_results"] = {
                lab: run_forwarded_launcher(root, lab)
                for lab in ("lab2", "lab3", "lab5")
            }
            self.context.lab_state["forwarded_launcher_results"]["lab4"] = (
                run_lab4_launcher(root)
            )
        elif subject == "Lab 3 deny-to-allow transition":
            root = self.context.lab_state["repository_root"]
            self.context.lab_state["lab3_launcher_result"] = (
                run_forwarded_launcher(root, "lab3")
            )
        elif subject == "CPU forward lifecycle":
            path = self.context.lab_state["cpu_sequence_path"]
            self.context.lab_state["cpu_sequence_events"] = (
                run_cpu_lab_sequence(path) if path.is_file() else []
            )
        elif subject == "CPU Lab 4 sequence":
            path = self.context.lab_state["cpu_sequence_path"]
            root = Path(__file__).parents[3]
            self.context.lab_state["cpu_lab4_sequence_events"] = (
                run_cpu_lab_sequence(path) if path.is_file() else []
            )
            self.context.lab_state["cpu_lab4_launcher"] = (
                root / "labs" / "lab4" / "run.sh"
            ).read_text(encoding="utf-8")
        elif subject == "GPU default lab":
            self.context.lab_state["generated_runner_default_lab5"] = (
                "lab=lab5" in self.context.lab_state["home_runner_installer"]
            )
        elif subject == "secret scanner fallback":
            secret, result = run_secret_scan_without_rg(
                self.context.lab_state["secret_scanner_path"]
            )
            self.context.lab_state["scanner_secret"] = secret
            self.context.lab_state["scanner_result"] = result
        elif subject == "tool validation recovery":
            self.context.lab_state["tool_retry"] = recoverable_tool_error(
                "inspect_linked_issue",
                self.context.lab_state["tool_error"],
                4,
                16,
            )
        elif subject == "secret search tool failure":
            self.context.lab_state["scanner_failure_result"] = (
                run_secret_scan_with_failing_search(
                    self.context.lab_state["secret_scanner_path"]
                )
            )
        elif subject == "repository safety":
            ignore = (
                Path(__file__).parents[3] / ".gitignore"
            ).read_text(encoding="utf-8").splitlines()
            self.context.lab_state["artifact_excluded"] = (
                self.context.lab_state["ignore_pattern"] in ignore
            )
        elif subject == "Streamlit model request":
            from openshell_lab.streamlit_inference import (
                MODEL_URL as streamlit_model_url,
                build_chat_request as build_streamlit_chat_request,
            )

            self.context.lab_state["streamlit_request"] = (
                build_streamlit_chat_request(
                    [{"role": "user", "content": "hello"}]
                )
            )
            self.context.lab_state["streamlit_model_url"] = streamlit_model_url
        elif subject == "Streamlit input validation":
            from openshell_lab.streamlit_inference import (
                build_chat_request as build_streamlit_chat_request,
            )

            try:
                build_streamlit_chat_request(
                    [
                        {
                            "role": "user",
                            "content": self.context.lab_state["streamlit_prompt"],
                        }
                    ]
                )
            except ValueError:
                self.context.lab_state["streamlit_input_rejected"] = True
            else:
                self.context.lab_state["streamlit_input_rejected"] = False
        elif subject == "Lab 4 network posture":
            self.context.lab_state["lab4_network_policies"] = (
                self.context.lab_state["policy"]["network_policies"]
            )
        elif subject == "Lab 4 forward configuration":
            text = self.context.lab_state["lab4_launcher"]
            create_position = text.find("openshell sandbox create")
            streamlit_position = text.find("nohup streamlit run app.py")
            forward_position = text.find(
                "openshell forward service openshell-lab4"
            )
            host_health_position = text.find(
                "http://127.0.0.1:18401/_stcore/health"
            )
            self.context.lab_state["lab4_forward_valid"] = (
                create_position >= 0
                and create_position < streamlit_position < forward_position
                and forward_position < host_health_position
                and "systemd-run --user" in text
                and "--target-port 8501" in text
                and "--local 127.0.0.1:18401" in text
                and "0.0.0.0:18401" not in text
            )
        elif subject == "verifier denial controls":
            text = self.context.lab_state["lab4_verifier"]
            self.context.lab_state["lab4_denial_controls_valid"] = all(
                marker in text
                for marker in (
                    "filesystem-write-denied",
                    "namespace-denied",
                    "filesystem denial probe failed",
                    "namespace denial probe failed",
                )
            )
        elif subject == "live listener controls":
            text = self.context.lab_state["lab4_verifier"]
            self.context.lab_state["lab4_listener_controls_valid"] = all(
                marker in text
                for marker in (
                    "systemctl --user show",
                    "ss -H -ltn",
                    'listeners != ["127.0.0.1:18401"]',
                )
            )
        elif subject == "Streamlit failed inference history":
            from openshell_lab.streamlit_inference import (
                MAX_HISTORY_MESSAGES,
                append_bounded_history,
            )

            history = [
                {"role": "user", "content": str(index)}
                for index in range(MAX_HISTORY_MESSAGES)
            ]
            self.context.lab_state["streamlit_failed_history"] = (
                append_bounded_history(
                    history,
                    {"role": "user", "content": "newest"},
                )
            )
        elif subject == "evidence integrity controls":
            text = self.context.lab_state["lab4_collector"]
            self.context.lab_state["lab4_evidence_integrity_valid"] = all(
                marker in text
                for marker in (
                    "expected-lab4-files.txt",
                    "actual-lab4-files.txt",
                    ".lab4-stage.",
                    ".lab4-previous.",
                )
            )
        else:
            raise AssertionError(f"subject not yet implemented: {subject}")

    def assert_managed_request(self):
        request = self.context.lab_state["request"]
        if MODEL_URL != "https://inference.local/v1/chat/completions":
            raise AssertionError(f"unexpected managed inference URL: {MODEL_URL}")
        if _contains_credential_or_model(request):
            raise AssertionError("managed request contains a model or credential field")

    def assert_streamlit_managed_request(self):
        request = self.context.lab_state["streamlit_request"]
        _require(
            self.context.lab_state["streamlit_model_url"]
            == "https://inference.local/v1/chat/completions",
            "Streamlit request does not target managed inference",
        )
        _require(
            set(request) == {"messages", "temperature", "max_completion_tokens"},
            "Streamlit request contains fields outside the approved contract",
        )
        _require(
            not _contains_credential_or_model(request),
            "Streamlit request contains a model or credential field",
        )

    def assert_streamlit_input_rejected(self):
        _require(
            self.context.lab_state["streamlit_input_rejected"] is True,
            "invalid Streamlit input reached model access",
        )

    def assert_lab4_network_policy_empty(self):
        _require(
            self.context.lab_state["lab4_network_policies"] == {},
            "Lab 4 grants ordinary network egress",
        )

    def assert_lab4_forward_loopback_only(self):
        _require(
            self.context.lab_state["lab4_forward_valid"] is True,
            "Lab 4 forward is not durable, ordered, and loopback-only",
        )

    def assert_lab4_denials_fail_closed(self):
        _require(
            self.context.lab_state["lab4_denial_controls_valid"] is True,
            "Lab 4 verifier does not distinguish denials from operational failures",
        )

    def assert_lab4_live_listener_loopback_only(self):
        _require(
            self.context.lab_state["lab4_listener_controls_valid"] is True,
            "Lab 4 verifier does not require a live loopback-only listener",
        )

    def assert_streamlit_history_bounded(self):
        from openshell_lab.streamlit_inference import MAX_HISTORY_MESSAGES

        history = self.context.lab_state["streamlit_failed_history"]
        _require(
            len(history) == MAX_HISTORY_MESSAGES
            and history[-1]["content"] == "newest",
            "failed inference allowed Streamlit history to exceed its bound",
        )

    def assert_lab4_evidence_integrity(self):
        _require(
            self.context.lab_state["lab4_evidence_integrity_valid"] is True,
            "Lab 4 collector can retain partial or mixed evidence",
        )

    def assert_generated_runner_defaults_to_lab5(self):
        _require(
            self.context.lab_state["generated_runner_default_lab5"] is True,
            "generated runner does not default to Lab 5",
        )

    def assert_nonroot_image(self):
        identity = self.context.lab_state["image_user"].split(":", 1)
        user = identity[0]
        group = identity[1] if len(identity) == 2 else None
        _require(
            user.isdigit() and (group is None or group.isdigit()),
            "image USER must be numeric",
        )
        _require(
            int(user) > 0 and (group is None or int(group) > 0),
            "image USER must be non-root",
        )

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
        _require(self.context.lab_state["artifact_excluded"] is True, "artifact is not excluded")

    def assert_cpu_settings(self):
        _require(self.context.lab_state["cpu_settings_valid"] is True, "CPU settings are invalid")

    def assert_cpu_launch_safety(self):
        _require(
            self.context.lab_state["cpu_launch_safety_valid"] is True,
            "CPU launch serialization or provisional state is missing",
        )

    def assert_gpu_settings(self):
        _require(self.context.lab_state["gpu_settings_valid"] is True, "GPU settings are invalid")

    def assert_gpu_sequence_limit(self, maximum_sequences):
        result = self.context.lab_state["gpu_profile_result"]
        _require(result.returncode == 0, result.stderr)
        actual_limit = result.stdout.strip().split()[-1]
        _require(
            actual_limit == maximum_sequences,
            f"expected maximum sequence limit {maximum_sequences}, got {actual_limit}",
        )

    def assert_gpu_profile_rejected(self):
        result = self.context.lab_state["gpu_profile_result"]
        _require(result.returncode != 0, "unsupported GPU topology was accepted")
        _require(
            "unsupported GPU topology" in result.stderr,
            "GPU topology rejection did not explain the failure",
        )

    def assert_latest_openshell_release(self):
        _require(
            self.context.lab_state["openshell_release_valid"] is True,
            "bootstrap does not select and verify the latest stable OpenShell release",
        )

    def assert_durable_canonical_processes(self):
        results = self.context.lab_state["durable_canonical_processes"]
        failures = [lab for lab, is_durable in results.items() if not is_durable]
        _require(
            not failures,
            "short-lived canonical process configured for: " + ", ".join(failures),
        )

    def assert_lab5_forward_cleanup(self):
        _require(
            self.context.lab_state["lab5_forward_cleanup_valid"] is True,
            "Lab 5 forward cleanup does not target the active sandbox",
        )

    def assert_lab1_upload_ordering(self):
        _require(
            self.context.lab_state["lab1_upload_ordering_valid"] is True,
            "Lab 1 source upload conflicts with creation or is out of order",
        )

    def assert_forwarded_launchers_release_session(self):
        results = self.context.lab_state["forwarded_launcher_results"]
        failures = [
            lab
            for lab, result in results.items()
            if not result.completed
            or result.returncode != 0
            or "sandbox-created" not in result.create_log
            or (
                lab == "lab4"
                and "forward-start" not in result.events
            )
            or (
                lab != "lab4"
                and "forward-ready" not in result.create_log
            )
        ]
        _require(
            not failures,
            "forwarded launchers retained the invoking session: "
            + ", ".join(failures),
        )

    def assert_lab3_deny_to_allow_transition(self):
        result = self.context.lab_state["lab3_launcher_result"]
        _require(result.completed, "Lab 3 launcher did not complete")
        _require(result.returncode == 0, f"Lab 3 launcher failed: {result.stderr}")
        _require(
            result.events
            == (
                "denied-network-probe",
                "denial-evidence-check",
                "report-absence-check",
                "policy-set",
                "report-agent",
            ),
            "Lab 3 did not bound denial and preserve the required transition order: "
            + ", ".join(result.events),
        )

    def assert_cpu_forward_sequence(self):
        events = self.context.lab_state["cpu_sequence_events"]
        _require(events, "CPU lab sequence runner is missing")
        lab2_verified = events.index("lab2-verify")
        lab2_stopped = events.index("forward-stop:18080:openshell-lab2")
        lab3_started = events.index("lab3-build")
        _require(
            lab2_verified < lab2_stopped < lab3_started,
            "Lab 2 forward was not stopped between Lab 2 verification and Lab 3",
        )

    def assert_cpu_lab4_sequence(self):
        events = self.context.lab_state["cpu_lab4_sequence_events"]
        _require("lab3-verify" in events, "CPU sequence omitted Lab 3 verification")
        _require("lab4-build" in events, "CPU sequence omitted Lab 4 build")
        _require(
            events.index("lab3-verify") < events.index("lab4-build"),
            "Lab 4 started before Lab 3 verification completed",
        )
        _require(
            events[-3:] == ["lab4-build", "lab4-run", "lab4-verify"],
            "CPU sequence does not finish with the Lab 4 lifecycle",
        )
        launcher = self.context.lab_state["cpu_lab4_launcher"]
        _require("18401" in launcher, "Lab 4 does not use its distinct port")
        _require("18080" not in launcher, "Lab 4 reuses the report forward")

    def assert_secret_scanner_fallback(self):
        result = self.context.lab_state["scanner_result"]
        secret = self.context.lab_state["scanner_secret"]
        output = result.stdout + result.stderr
        _require(result.returncode != 0, "secret scanner falsely reported clean")
        _require("unsafe.txt" in result.stdout, "scanner omitted the unsafe path")
        _require("command not found" not in result.stderr, "scanner invoked missing rg")
        _require(secret not in output, "scanner exposed credential content")

    def assert_bounded_tool_retry(self):
        result = self.context.lab_state["tool_retry"]
        _require(result["retry"] is True, "tool error is not recoverable")
        _require(
            "explicitly referenced" in result["detail"],
            "retry guidance omitted the evidence boundary",
        )
        try:
            recoverable_tool_error(
                "inspect_linked_issue",
                self.context.lab_state["tool_error"],
                16,
                16,
            )
        except ValueError:
            return
        raise AssertionError("tool validation remained recoverable past the call limit")

    def assert_secret_search_failure(self):
        result = self.context.lab_state["scanner_failure_result"]
        _require(result.returncode == 2, "search tool error did not fail the scan")
        _require("search failed" in result.stderr, "search failure was not reported")
        _require("secret-scan: clean" not in result.stdout, "scan falsely reported clean")
