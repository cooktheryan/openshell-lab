from pathlib import Path
import unittest

from test_support.shell_lab_harness import (
    EVIDENCE_FILENAMES,
    evidence_archive_members,
    generated_runner_default_lab,
    run_cpu_lab_sequence,
    run_evidence_collector,
)


ROOT = Path(__file__).parents[1]
DEPLOY = ROOT / "scripts" / "deploy-cpu.sh"
COLLECT = ROOT / "scripts" / "collect-evidence.sh"
COLLECT_GPU = ROOT / "scripts" / "collect-gpu-evidence.sh"
OCR = ROOT / "review" / "run-ocr.sh"
CPU_SEQUENCE = ROOT / "infra" / "remote" / "run-cpu-labs.sh"
RUNNER_INSTALLER = ROOT / "infra" / "remote" / "install-runner.sh"


class DeploymentOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in (DEPLOY, COLLECT, OCR):
            if not path.is_file():
                raise AssertionError(f"missing {path}")
        cls.deploy = DEPLOY.read_text(encoding="utf-8")
        cls.collect = COLLECT.read_text(encoding="utf-8")
        cls.collect_gpu = (
            COLLECT_GPU.read_text(encoding="utf-8")
            if COLLECT_GPU.is_file()
            else ""
        )

    def _run_gpu_collector(self, members, existing_files=None, lock_held=False):
        outcome = run_evidence_collector(
            ROOT,
            "GPU",
            members,
            existing_files=existing_files,
            lock_held=lock_held,
        )
        return outcome.process, outcome.collected

    def test_pipeline_uses_strict_failure_handling_and_required_order(self):
        self.assertIn("set -euo pipefail", self.deploy)
        markers = [
            "launch-cpu.sh",
            "wait_for_ssh",
            "rsync",
            "bootstrap-rhel10.sh",
            "configure_openai",
            "infra/remote/run-cpu-labs.sh",
            "scan-secrets.sh",
            "collect-evidence.sh",
        ]
        positions = [self.deploy.index(marker) for marker in markers]
        self.assertEqual(sorted(positions), positions)

    def test_cpu_sequence_releases_lab2_forward_before_lab3(self):
        self.assertTrue(CPU_SEQUENCE.is_file(), f"missing {CPU_SEQUENCE}")
        events = run_cpu_lab_sequence(CPU_SEQUENCE)
        self.assertLess(
            events.index("lab2-verify"),
            events.index("forward-stop:18080:openshell-lab2"),
        )
        self.assertLess(
            events.index("forward-stop:18080:openshell-lab2"),
            events.index("lab3-build"),
        )

    def test_cpu_sequence_runs_lab4_after_lab3_verification(self):
        cpu_sequence = CPU_SEQUENCE.read_text(encoding="utf-8")
        self.assertIn("./labs/lab4/build.sh", cpu_sequence)
        self.assertNotIn("./labs/lab5/", cpu_sequence)
        events = run_cpu_lab_sequence(CPU_SEQUENCE)
        self.assertIn("lab4-build", events)
        self.assertLess(events.index("lab3-verify"), events.index("lab4-build"))
        self.assertEqual(
            ["lab4-build", "lab4-run", "lab4-verify"],
            events[-3:],
        )

    def test_runner_defaults_to_lab5_when_vllm_is_active(self):
        self.assertEqual("lab5", generated_runner_default_lab(RUNNER_INSTALLER))

    def test_ssh_uses_repository_known_hosts_and_strict_checking(self):
        for expected in (
            "state/known_hosts",
            "StrictHostKeyChecking=yes",
            "UserKnownHostsFile=",
            "ssh-keyscan",
        ):
            self.assertIn(expected, self.deploy + self.collect)

    def test_rsync_excludes_secrets_state_and_large_artifacts(self):
        for excluded in (
            ".env",
            "state/",
            "*.key",
            "*.pem",
            ".venv/",
            "models/",
            "*.safetensors",
        ):
            self.assertIn(excluded, self.deploy)

    def test_credential_step_requires_environment_or_interactive_tty(self):
        self.assertIn("OPENAI_API_KEY", self.deploy)
        self.assertIn("-t 0", self.deploy)
        self.assertIn("read -r -s", self.deploy)
        self.assertIn("credential input requires a TTY", self.deploy)
        self.assertNotIn("OPENAI_API_KEY=", self.deploy)

    def test_evidence_collection_is_sanitized_and_bounded(self):
        self.assertIn("evidence/cpu", self.collect)
        self.assertIn("redact", self.collect)
        self.assertIn("sha256", self.collect)
        self.assertIn("systemctl", self.collect)
        self.assertIn("openshell", self.collect)
        self.assertNotIn("provider get", self.collect)
        self.assertNotIn("credentials", self.collect.lower())

    def test_lab4_evidence_is_archived_then_redacted_as_text(self):
        self.assertIn(
            'tar -C "$repository/evidence/cpu" -cf - lab4', self.collect
        )
        self.assertNotIn("evidence/cpu -cf - lab5", self.collect)
        self.assertIn('redact <"$source" >"$destination"', self.collect)
        self.assertNotIn("openshell provider get", self.collect)
        self.assertNotIn("printenv", self.collect)

    def test_lab4_evidence_requires_a_complete_set_and_replaces_stale_files(self):
        for marker in (
            "expected-lab4-files.txt",
            "actual-lab4-files.txt",
            "Lab 4 evidence artifact set is incomplete or unexpected",
            ".lab4-stage.",
            ".lab4-previous.",
        ):
            self.assertIn(marker, self.collect)

    def test_gpu_evidence_collection_is_sanitized_bounded_and_atomic(self):
        for marker in (
            "StrictHostKeyChecking=yes",
            "expected-gpu-files.txt",
            "actual-gpu-files.txt",
            "agent-result.json",
            "sandbox-create.log",
            "gpus.txt",
            "policy.json",
        ):
            self.assertIn(marker, self.collect_gpu)
        self.assertNotIn("openshell provider get", self.collect_gpu)
        self.assertNotIn("printenv", self.collect_gpu)

    def test_gpu_evidence_redacts_each_file_and_replaces_stale_files(self):
        secret_key = "secret-value-" + "C" * 32
        session_token = "session-value-" + "D" * 64
        payloads = (
            ("sk-" + "A" * 24, "AS" + "IA" + "E" * 16),
            ("AK" + "IA" + "B" * 16,),
            (("AWS_" + "SECRET_ACCESS_KEY") + f"={secret_key}",),
            (
                ("AWS_" + "SESSION_TOKEN") + f"={session_token}",
                "Authorization: Bearer hidden-value",
                "Authorization: Basic hidden-value",
            ),
        )
        filenames = (
            "agent-result.json",
            "gpus.txt",
            "policy.json",
            "sandbox-create.log",
        )
        members = [
            (f"gpu/{name}", f"safe-{index} {' '.join(payloads[index])}\n", "file")
            for index, name in enumerate(filenames)
        ]

        result, collected = self._run_gpu_collector(members)

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        self.assertEqual(set(filenames), set(collected))
        for index, name in enumerate(filenames):
            self.assertIn(f"safe-{index}", collected[name])
            self.assertIn("[REDACTED]", collected[name])
            for secret in payloads[index]:
                if "=" in secret:
                    secret = secret.split("=", maxsplit=1)[1]
                self.assertNotIn(secret, collected[name])

    def test_gpu_evidence_refuses_collection_while_repository_lock_is_held(self):
        required = [
            (f"gpu/{name}", "new evidence\n", "file")
            for name in (
                "agent-result.json",
                "gpus.txt",
                "policy.json",
                "sandbox-create.log",
            )
        ]

        result, collected = self._run_gpu_collector(required, lock_held=True)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("GPU evidence collection is already running", result.stderr)
        self.assertEqual({"stale.txt": "prior evidence\n"}, collected)

    def test_gpu_evidence_rejects_unsafe_or_mixed_archives_without_replacement(self):
        required = [
            (f"gpu/{name}", "safe\n", "file")
            for name in (
                "agent-result.json",
                "gpus.txt",
                "policy.json",
                "sandbox-create.log",
            )
        ]
        invalid_members = {
            "absolute": required + [("/escape", "unsafe\n", "file")],
            "out of scope": required + [("other/file", "unsafe\n", "file")],
            "traversal": required + [("gpu/../escape", "unsafe\n", "file")],
            "symlink": required + [("gpu/link", "policy.json", "symlink")],
            "special file": required + [("gpu/fifo", "", "fifo")],
            "mixed set": required + [("gpu/unexpected.txt", "mixed\n", "file")],
            "many out of scope": required
            + [
                (f"other/rejected-{index:05d}-" + "x" * 48, "unsafe\n", "file")
                for index in range(4096)
            ],
        }
        for label, members in invalid_members.items():
            with self.subTest(label=label):
                result, collected = self._run_gpu_collector(members)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual({"stale.txt": "prior evidence\n"}, collected)

    def test_collectors_accept_one_occurrence_of_each_exact_artifact(self):
        for collector in ("CPU", "GPU"):
            with self.subTest(collector=collector):
                directory = "lab4/" if collector == "CPU" else "gpu/"
                outcome = run_evidence_collector(
                    ROOT,
                    collector,
                    [(directory, "", "directory")]
                    + evidence_archive_members(collector),
                )
                self.assertEqual(
                    0,
                    outcome.process.returncode,
                    outcome.process.stdout + outcome.process.stderr,
                )
                self.assertEqual(
                    set(EVIDENCE_FILENAMES[collector]),
                    set(outcome.collected),
                )

    def test_collectors_reject_duplicate_members_without_replacement(self):
        for collector in ("CPU", "GPU"):
            with self.subTest(collector=collector):
                members = evidence_archive_members(collector)
                members.append(members[0])
                outcome = run_evidence_collector(ROOT, collector, members)
                self.assertNotEqual(0, outcome.process.returncode)
                self.assertIn("duplicate", outcome.process.stderr.lower())
                self.assertEqual(
                    {"stale.txt": "prior evidence\n"}, outcome.collected
                )

    def test_collectors_fail_closed_when_remote_directory_selection_fails(self):
        for collector in ("CPU", "GPU"):
            with self.subTest(collector=collector):
                outcome = run_evidence_collector(
                    ROOT,
                    collector,
                    evidence_archive_members(collector),
                    remote_directory_missing=True,
                )
                self.assertNotEqual(0, outcome.process.returncode)
                self.assertEqual(
                    {"stale.txt": "prior evidence\n"}, outcome.collected
                )

    def test_cpu_scope_validation_consumes_large_invalid_member_list(self):
        members = evidence_archive_members("CPU")
        members.extend(
            (f"other/rejected-{index:05d}-" + "x" * 48, "unsafe\n", "file")
            for index in range(4096)
        )

        outcome = run_evidence_collector(ROOT, "CPU", members)

        self.assertNotEqual(0, outcome.process.returncode)
        self.assertIn("out-of-scope", outcome.process.stderr)
        self.assertEqual({"stale.txt": "prior evidence\n"}, outcome.collected)

    def test_cpu_evidence_redacts_each_aws_credential_form_from_every_file(self):
        values = (
            "AS" + "IA" + "A" * 16,
            "synthetic-secret-" + "S" * 32,
            "synthetic-session-" + "T" * 64,
        )
        payload = " ".join(
            (
                values[0],
                ("AWS_" + "SECRET_ACCESS_KEY") + "=" + values[1],
                ("AWS_" + "SESSION_TOKEN") + ": " + values[2],
            )
        )
        outcome = run_evidence_collector(
            ROOT,
            "CPU",
            evidence_archive_members("CPU", payload + "\n"),
        )

        self.assertEqual(
            0,
            outcome.process.returncode,
            outcome.process.stdout + outcome.process.stderr,
        )
        self.assertEqual(set(EVIDENCE_FILENAMES["CPU"]), set(outcome.collected))
        for content in outcome.collected.values():
            self.assertIn("[REDACTED]", content)
            for value in values:
                self.assertNotIn(value, content)

    def test_cpu_evidence_refuses_publication_while_lock_is_held(self):
        outcome = run_evidence_collector(
            ROOT,
            "CPU",
            evidence_archive_members("CPU"),
            lock_held=True,
        )

        self.assertNotEqual(0, outcome.process.returncode)
        self.assertIn(
            "CPU evidence collection is already running", outcome.process.stderr
        )
        self.assertEqual({"stale.txt": "prior evidence\n"}, outcome.collected)
        self.assertEqual((), outcome.ssh_commands)

    def test_ocr_script_reviews_security_and_correctness(self):
        text = OCR.read_text(encoding="utf-8")
        self.assertIn("ocr scan", text)
        for topic in (
            "security",
            "correctness",
            "least privilege",
            "secret handling",
            "documentation accuracy",
        ):
            self.assertIn(topic, text.lower())


if __name__ == "__main__":
    unittest.main()
