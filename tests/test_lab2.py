import json
from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).parents[1]
POLICY = ROOT / "policies" / "lab2-webroot-only.yaml"
LAB = ROOT / "labs" / "lab2"
HTTPD = ROOT / "infra" / "remote" / "openshell-lab-httpd.conf"


class Lab2ArtifactTests(unittest.TestCase):
    def test_run_waits_for_async_sandbox_deletion(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        self.assertIn("while openshell sandbox list --names", text)

    @classmethod
    def setUpClass(cls):
        if not POLICY.is_file():
            raise AssertionError(f"missing {POLICY}")
        cls.policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))

    def test_webroot_and_runtime_scratch_are_writable_and_landlock_is_required(self):
        filesystem = self.policy["filesystem_policy"]
        self.assertFalse(filesystem["include_workdir"])
        self.assertEqual(
            ["/var/www/html", "/tmp", "/dev/null"], filesystem["read_write"]
        )
        self.assertEqual("hard_requirement", self.policy["landlock"]["compatibility"])
        for required in ("/usr", "/lib64", "/etc", "/proc", "/opt/openshell-lab"):
            self.assertIn(required, filesystem["read_only"])

    def test_network_policy_remains_github_only(self):
        policies = self.policy["network_policies"]
        self.assertEqual(["github_api_readonly"], list(policies))
        entry = policies["github_api_readonly"]
        self.assertEqual([{"path": "/usr/bin/curl"}], entry["binaries"])
        self.assertEqual("api.github.com", entry["endpoints"][0]["host"])
        self.assertEqual("read-only", entry["endpoints"][0]["access"])

    def test_run_uses_only_the_reviewed_webroot_bind_mount(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        self.assertIn('--from "$IMAGE"', text)
        self.assertNotIn("--upload", text)
        match = re.search(r"(?m)^\s*(?:export\s+)?DRIVER_CONFIG='([^']+)'\s*$", text)
        self.assertIsNotNone(match)
        config = json.loads(match.group(1))
        self.assertEqual(
            {
                "podman": {
                    "mounts": [
                        {
                            "type": "bind",
                            "source": "/var/www/html/openshell-lab",
                            "target": "/var/www/html",
                            "read_only": False,
                            "selinux_label": "private",
                        }
                    ]
                }
            },
            config,
        )

    def test_host_configuration_enables_bind_mount_and_http_proxy(self):
        configure = (LAB / "configure-host.sh").read_text(encoding="utf-8")
        self.assertIn("enable_bind_mounts = true", configure)
        self.assertIn("for _ in $(seq 1 30)", configure)
        self.assertIn("openshell status >/dev/null 2>&1", configure)
        self.assertIn("/var/www/html/openshell-lab", configure)
        self.assertIn('sudo chown -R "$USER:$USER" /var/www/html/openshell-lab', configure)
        self.assertIn("podman unshare chown -R 1500:1500", configure)
        self.assertLess(
            configure.index('sudo chown -R "$USER:$USER"'),
            configure.index("podman unshare chown"),
        )
        self.assertIn("httpd_can_network_connect", configure)
        self.assertIn("systemctl reload httpd", configure)
        self.assertTrue(HTTPD.is_file())
        httpd = HTTPD.read_text(encoding="utf-8")
        self.assertIn("ProxyPass /openshell-lab/ http://127.0.0.1:18080/", httpd)

    def test_verifier_checks_allowed_and_denied_writes_and_http(self):
        text = (LAB / "verify.sh").read_text(encoding="utf-8")
        for expected in (
            "/var/www/html",
            "/sandbox",
            "/tmp",
            "http://127.0.0.1/openshell-lab/",
            "nvidia-openshell-last-5-merges.md",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
