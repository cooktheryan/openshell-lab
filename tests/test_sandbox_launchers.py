from pathlib import Path
import unittest

from test_support.shell_lab_harness import run_forwarded_launcher, run_lab5_launcher


ROOT = Path(__file__).parents[1]


class SandboxLauncherTests(unittest.TestCase):
    def test_forwarded_launchers_release_the_invoking_session(self):
        for lab in ("lab2", "lab3", "lab4"):
            with self.subTest(lab=lab):
                result = run_forwarded_launcher(ROOT, lab)
                self.assertTrue(
                    result.completed,
                    f"{lab} retained the invoking session output pipe",
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("sandbox-created", result.create_log)
                self.assertIn("forward-ready", result.create_log)

    def test_all_labs_keep_the_canonical_process_running(self):
        for lab in ("lab1", "lab2", "lab3", "lab4", "lab5"):
            with self.subTest(lab=lab):
                run_path = ROOT / "labs" / lab / "run.sh"
                self.assertTrue(run_path.is_file(), f"{lab} launcher is missing")
                text = run_path.read_text(encoding="utf-8")
                self.assertIn("-- /usr/bin/sleep infinity", text)
                self.assertNotIn("-- /bin/true", text)

    def test_lab4_launcher_delegates_its_forward_and_releases_the_session(self):
        streamlit_run = (ROOT / "labs" / "lab4" / "run.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("--local 127.0.0.1:18401", streamlit_run)
        self.assertIn('SANDBOX="openshell-lab4"', streamlit_run)
        result = run_lab5_launcher(ROOT)

        self.assertTrue(result.completed, result.stderr)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            (
                "sandbox-create",
                "streamlit-start",
                "internal-health",
                "forward-start",
                "host-health",
            ),
            result.events,
        )

    def test_lab5_stops_only_its_active_sandbox_forward(self):
        gpu_run = (ROOT / "labs" / "lab5" / "run.sh").read_text(encoding="utf-8")
        self.assertIn('SANDBOX="openshell-lab5"', gpu_run)
        self.assertIn("openshell sandbox create", gpu_run)
        self.assertIn("--forward 127.0.0.1:18080", gpu_run)
        self.assertIn("localhost/openshell-lab-agent:lab5", gpu_run)
        self.assertIn('openshell forward stop 18080 "$SANDBOX"', gpu_run)
        self.assertNotIn("openshell forward stop 18080 openshell-lab3", gpu_run)

    def test_lab1_uploads_source_after_creation_and_before_agent_execution(self):
        text = (ROOT / "labs" / "lab1" / "run.sh").read_text(encoding="utf-8")
        self.assertNotIn('--upload "$ROOT/src:/sandbox"', text)
        upload = next(
            line
            for line in text.splitlines()
            if line.startswith("openshell sandbox upload ")
        )
        self.assertEqual(
            'openshell sandbox upload "$SANDBOX" "$ROOT/src" /sandbox >/dev/null',
            upload,
        )
        self.assertLess(text.index("openshell sandbox create"), text.index(upload))
        self.assertLess(text.index(upload), text.index("openshell sandbox exec"))

    def test_lab3_bounds_denial_before_one_allowed_report_agent_run(self):
        result = run_forwarded_launcher(ROOT, "lab3")

        self.assertTrue(result.completed, "Lab 3 launcher did not complete")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            (
                "denied-network-probe",
                "denial-evidence-check",
                "report-absence-check",
                "policy-set",
                "report-agent",
            ),
            result.events,
        )

    def test_lab3_probe_operational_error_fails_before_policy_set(self):
        result = run_forwarded_launcher(
            ROOT,
            "lab3",
            lab3_probe_mode="operational-error",
        )

        self.assertTrue(result.completed, "Lab 3 launcher did not complete")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("network-probe-error", result.events)
        self.assertNotIn("policy-set", result.events)

    def test_lab3_report_check_error_fails_before_policy_set(self):
        result = run_forwarded_launcher(
            ROOT,
            "lab3",
            lab3_report_check_status=2,
        )

        self.assertTrue(result.completed, "Lab 3 launcher did not complete")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("report-check-error", result.events)
        self.assertNotIn("policy-set", result.events)

    def test_lab3_existing_report_fails_before_policy_set(self):
        result = run_forwarded_launcher(
            ROOT,
            "lab3",
            lab3_report_check_status=0,
        )

        self.assertTrue(result.completed, "Lab 3 launcher did not complete")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("report-present-check", result.events)
        self.assertNotIn("policy-set", result.events)


if __name__ == "__main__":
    unittest.main()
