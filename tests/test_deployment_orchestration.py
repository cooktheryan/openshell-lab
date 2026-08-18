from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
DEPLOY = ROOT / "scripts" / "deploy-cpu.sh"
COLLECT = ROOT / "scripts" / "collect-evidence.sh"
OCR = ROOT / "review" / "run-ocr.sh"


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
            "labs/lab1/run.sh",
            "labs/lab2/run.sh",
            "labs/lab3/run.sh",
            "scan-secrets.sh",
            "collect-evidence.sh",
        ]
        positions = [self.deploy.index(marker) for marker in markers]
        self.assertEqual(sorted(positions), positions)

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
