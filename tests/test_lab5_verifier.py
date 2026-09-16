from pathlib import Path
import unittest

from test_support.shell_lab_harness import run_lab5_verifier


ROOT = Path(__file__).parents[1]


class Lab5VerifierTests(unittest.TestCase):
    def test_expected_security_denials_and_loopback_listener_pass(self):
        result = run_lab5_verifier(ROOT)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("lab4 verification passed", result.stdout)

    def test_filesystem_probe_operational_error_fails(self):
        result = run_lab5_verifier(ROOT, filesystem_mode="operational-error")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("filesystem denial probe failed", result.stderr)

    def test_namespace_probe_operational_error_fails(self):
        result = run_lab5_verifier(ROOT, namespace_mode="operational-error")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("namespace denial probe failed", result.stderr)

    def test_public_live_listener_fails_even_if_unit_claims_loopback(self):
        result = run_lab5_verifier(ROOT, listener_bind="0.0.0.0:18401")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unexpected Lab 4 listeners", result.stderr)

    def test_public_unit_bind_fails(self):
        result = run_lab5_verifier(ROOT, unit_bind="0.0.0.0:18401")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("public bind", result.stderr)


if __name__ == "__main__":
    unittest.main()
