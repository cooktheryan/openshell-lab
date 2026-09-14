import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).parents[1]
LAB = ROOT / "labs" / "lab3"
POLICIES = ROOT / "policies"


class Lab3ArtifactTests(unittest.TestCase):
    def test_run_waits_for_async_sandbox_deletion(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        self.assertIn("while openshell sandbox list --names", text)

    @classmethod
    def setUpClass(cls):
        cls.deny_path = POLICIES / "lab3-network-deny.yaml"
        cls.allow_path = POLICIES / "lab3-github-allow.yaml"
        if not cls.deny_path.is_file() or not cls.allow_path.is_file():
            raise AssertionError("Lab 3 policies are missing")
        cls.deny = yaml.safe_load(cls.deny_path.read_text(encoding="utf-8"))
        cls.allow = yaml.safe_load(cls.allow_path.read_text(encoding="utf-8"))

    def test_both_policies_retain_identical_lab2_static_posture(self):
        for key in ("version", "filesystem_policy", "landlock"):
            self.assertEqual(self.deny[key], self.allow[key])
        self.assertEqual(
            ["/var/www/html", "/tmp", "/dev/null"],
            self.deny["filesystem_policy"]["read_write"],
        )
        self.assertEqual("hard_requirement", self.deny["landlock"]["compatibility"])

    def test_deny_has_no_network_capability(self):
        self.assertEqual({}, self.deny["network_policies"])

    def test_allow_contains_only_github_curl_read_access(self):
        self.assertEqual(["github_api_readonly"], list(self.allow["network_policies"]))
        entry = self.allow["network_policies"]["github_api_readonly"]
        self.assertEqual([{"path": "/usr/bin/curl"}], entry["binaries"])
        self.assertEqual("api.github.com", entry["endpoints"][0]["host"])
        self.assertEqual("read-only", entry["endpoints"][0]["access"])

    def test_run_hot_sets_allow_after_proving_deny(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        deny_position = text.index("lab3-network-deny.yaml")
        allow_position = text.index("openshell policy set")
        self.assertLess(deny_position, allow_position)
        self.assertIn("lab3-github-allow.yaml", text)
        self.assertIn("--wait", text)
        self.assertIn("expected denied GitHub probe was blocked", text)
        self.assertIn("--timeout 30", text)
        self.assertIn("--max-time 20", text)

    def test_run_uses_reviewed_webroot_bind(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        self.assertIn("--forward 127.0.0.1:18080", text)
        self.assertIn("python3 -m http.server 18080", text)
        line = next(line for line in text.splitlines() if line.startswith("DRIVER_CONFIG="))
        config = json.loads(line.split("=", 1)[1].strip("'"))
        mounts = config["podman"]["mounts"]
        self.assertEqual(1, len(mounts))
        self.assertEqual("/var/www/html/openshell-lab", mounts[0]["source"])
        self.assertEqual("/var/www/html", mounts[0]["target"])

    def test_run_stops_its_own_forward_and_confirms_denied_report_absence(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        self.assertIn("openshell forward stop 18080 openshell-lab3", text)
        self.assertNotIn("openshell forward stop 18080 openshell-lab2", text)
        self.assertIn('podman unshare rm -f "$REPORT_HOST_PATH"', text)
        self.assertIn('podman unshare test -e "$REPORT_HOST_PATH"', text)

    def test_build_and_verify_inspect_nonroot_identity(self):
        for name in ("build.sh", "run.sh", "verify.sh"):
            self.assertTrue((LAB / name).is_file())
        combined = (LAB / "build.sh").read_text() + (LAB / "verify.sh").read_text()
        self.assertIn(".Config.User", combined)
        self.assertIn("1500:1500", combined)

    def test_verification_leaves_the_live_sandbox_running(self):
        text = (LAB / "verify.sh").read_text(encoding="utf-8")
        self.assertNotIn('sandbox delete "$SANDBOX"', text)

    def test_verifier_reads_owner_only_report_through_http(self):
        text = (LAB / "verify.sh").read_text(encoding="utf-8")
        self.assertIn("published_report=$(mktemp)", text)
        self.assertNotIn('grep -F \'# NVIDIA/OpenShell\' "$REPORT"', text)
        self.assertIn("grep -c '^## PR #[0-9]", text)


if __name__ == "__main__":
    unittest.main()
