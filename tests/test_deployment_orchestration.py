from pathlib import Path
import unittest

from test_support.shell_lab_harness import run_cpu_lab_sequence


ROOT = Path(__file__).parents[1]
DEPLOY = ROOT / "scripts" / "deploy-cpu.sh"
COLLECT = ROOT / "scripts" / "collect-evidence.sh"
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
        runner_installer = RUNNER_INSTALLER.read_text(encoding="utf-8")
        self.assertIn("lab=lab5", runner_installer)

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
        self.assertIn("tar -C evidence/cpu -cf - lab4", self.collect)
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
