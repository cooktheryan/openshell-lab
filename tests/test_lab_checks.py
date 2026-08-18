from types import SimpleNamespace
from types import ModuleType
import sys
import unittest

fake_behave = ModuleType("behave")
fake_behave.given = lambda _pattern: (lambda function: function)
fake_behave.when = lambda _pattern: (lambda function: function)
fake_behave.then = lambda _pattern: (lambda function: function)
sys.modules.setdefault("behave", fake_behave)

import features.steps  # noqa: F401
from features.steps.support.lab_checks import LabChecks


class LabCheckHardeningTests(unittest.TestCase):
    def test_traversal_never_inherits_a_writable_prefix(self):
        context = SimpleNamespace(
            lab_state={"policy": {"filesystem_policy": {"read_write": ["/tmp"]}}}
        )
        checks = LabChecks(context)
        checks.evaluate_filesystem_write("/tmp/../etc/passwd")
        self.assertEqual("denied", context.lab_state["filesystem_action"])

    def test_managed_request_rejects_nested_case_insensitive_secret_keys(self):
        context = SimpleNamespace(
            lab_state={"request": {"headers": {"Authorization": "Bearer fixture"}}}
        )
        with self.assertRaises(AssertionError):
            LabChecks(context).assert_managed_request()

    def test_missing_container_user_has_an_explicit_failure(self):
        context = SimpleNamespace(lab_state={"containerfile": "FROM example.test/base"})
        with self.assertRaisesRegex(AssertionError, "USER directive"):
            LabChecks(context).evaluate_subject("image identity")

    def test_step_modules_keep_package_qualified_names(self):
        self.assertIn("features.steps.given.the_policy_is_loaded", sys.modules)
        self.assertIn("features.steps.then.the_network_action_should_be", sys.modules)

    def test_gpu_configuration_is_loaded_from_deployment_artifacts(self):
        context = SimpleNamespace(lab_state={})
        checks = LabChecks(context)
        checks.load_configuration("GPU deployment")
        checks.evaluate_subject("GPU inference configuration")
        self.assertTrue(context.lab_state["gpu_settings_valid"])
        self.assertIn("--tensor-parallel-size 4", context.lab_state["gpu_config"])

    def test_unknown_report_status_is_rejected(self):
        context = SimpleNamespace(lab_state={"report_status": "accepted"})
        with self.assertRaisesRegex(AssertionError, "unsupported report status"):
            LabChecks(context).assert_report_status("typo")

    def test_complete_report_fixture_renders_associated_issues(self):
        context = SimpleNamespace(lab_state={})
        LabChecks(context).load_report_fixture("complete")
        self.assertIn("- Associated issues: #50 (open)", context.lab_state["markdown"])


if __name__ == "__main__":
    unittest.main()
