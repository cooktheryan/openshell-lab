from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).parents[1]
POLICY = ROOT / "policies" / "lab1-github-only-baseline-filesystem.yaml"
LAB = ROOT / "labs" / "lab1"


class Lab1ArtifactTests(unittest.TestCase):
    def test_run_waits_for_async_sandbox_deletion(self):
        text = (LAB / "run.sh").read_text(encoding="utf-8")
        self.assertIn("while openshell sandbox list --names", text)

    @classmethod
    def setUpClass(cls):
        if not POLICY.is_file():
            raise AssertionError(f"missing {POLICY}")
        cls.policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))

    def test_filesystem_configuration_uses_the_openshell_baseline(self):
        self.assertEqual(1, self.policy["version"])
        filesystem = self.policy["filesystem_policy"]
        self.assertTrue(filesystem["include_workdir"])
        self.assertIn("/usr", filesystem["read_only"])
        self.assertIn("/tmp", filesystem["read_write"])
        self.assertEqual("best_effort", self.policy["landlock"]["compatibility"])

    def test_network_allows_only_read_only_github_for_curl(self):
        policies = self.policy["network_policies"]
        self.assertEqual(["github_api_readonly"], list(policies))
        github = policies["github_api_readonly"]
        self.assertEqual([{"path": "/usr/bin/curl"}], github["binaries"])
        self.assertEqual(1, len(github["endpoints"]))
        endpoint = github["endpoints"][0]
        self.assertEqual("api.github.com", endpoint["host"])
        self.assertEqual(443, endpoint["port"])
        self.assertEqual("rest", endpoint["protocol"])
        self.assertEqual("enforce", endpoint["enforcement"])
        self.assertEqual("read-only", endpoint["access"])

    def test_scripts_exist_and_do_not_assign_openai_credentials(self):
        for name in ("configure-openai.sh", "run.sh", "verify.sh"):
            path = LAB / name
            self.assertTrue(path.is_file(), f"missing {path}")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("OPENAI_API_KEY=", text)
            self.assertNotIn("sk-", text)

    def test_openai_configuration_uses_bare_lookup_and_validates_gpt55(self):
        text = (LAB / "configure-openai.sh").read_text(encoding="utf-8")
        self.assertIn("--credential OPENAI_API_KEY", text)
        self.assertIn("--model gpt-5.5", text)
        self.assertIn("unset OPENAI_API_KEY", text)
        self.assertNotIn("--no-verify", text)

    def test_verifier_covers_two_denials_and_filesystem_noop(self):
        text = (LAB / "verify.sh").read_text(encoding="utf-8")
        for expected in (
            "api.github.com",
            "example.com",
            "python3",
            "--request POST",
            "/sandbox",
            "/tmp",
            "Landlock ruleset built",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
