from pathlib import Path
import unittest

from test_support.shell_lab_harness import run_cpu_start


ROOT = Path(__file__).parents[1]
AWS = ROOT / "infra" / "aws"


class AwsScriptTests(unittest.TestCase):
    def read(self, name):
        path = AWS / name
        self.assertTrue(path.is_file(), f"missing {path}")
        return path.read_text(encoding="utf-8")

    def test_launcher_uses_approved_cpu_configuration(self):
        text = self.read("launch-cpu.sh") + self.read("lib.sh")
        for expected in (
            "us-east-1",
            "ami-00adafae70b8029d8",
            "t3.micro",
            "rcook",
            "wide",
            "is-default",
            "HttpTokens=required",
            '"VolumeType":"gp3"',
            '"Encrypted":true',
            "openshell-four-labs",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("MarketType=spot", text)
        self.assertIn("--count 1", text)

    def test_launcher_waits_for_both_health_states_and_writes_private_state(self):
        text = self.read("launch-cpu.sh") + self.read("lib.sh")
        self.assertIn("instance-running", text)
        self.assertIn("instance-status-ok", text)
        self.assertIn("umask 077", text)
        self.assertIn("cpu-connection.env", text)
        self.assertIn("mv", text)

    def test_launcher_serializes_and_persists_identity_before_health_waits(self):
        launch = self.read("launch-cpu.sh")
        self.assertIn('launch_lock="${STATE_FILE}.launch.lock"', launch)
        self.assertIn('mkdir -- "$launch_lock"', launch)
        self.assertLess(
            launch.index('write_cpu_state "$instance_id"'),
            launch.index("ec2 wait instance-running"),
        )

    def test_state_loader_validates_all_values_used_by_start(self):
        common = self.read("lib.sh")
        self.assertIn('SUBNET_ID=$(state_value SUBNET_ID)', common)
        self.assertIn('SECURITY_GROUP_ID=$(state_value SECURITY_GROUP_ID)', common)
        self.assertIn('^subnet-[0-9a-f]+$', common)
        self.assertIn('^sg-[0-9a-f]+$', common)

    def test_lifecycle_scripts_resolve_and_validate_before_mutation(self):
        common = self.read("lib.sh")
        stop = self.read("stop-cpu.sh")
        start = self.read("start-cpu.sh")
        describe = self.read("describe-cpu.sh")
        self.assertIn("describe-tags", common)
        self.assertIn("openshell-four-labs", common)
        for script in (start, stop, describe):
            self.assertIn("load_cpu_state", script)
        self.assertIn("validate_cpu_instance", start)
        for script in (stop, describe):
            self.assertIn("validate_project_instance", script)
        self.assertIn("stop-instances", stop)
        self.assertLess(stop.index("validate_project_instance"), stop.index("stop-instances"))
        self.assertLess(start.index("validate_cpu_instance"), start.index("start-instances"))
        self.assertNotIn("terminate-instances", stop + start + describe)
        self.assertIn("start-instances", start)
        self.assertIn("describe-instances", describe)

    def test_start_rejects_mismatched_instance_type_before_mutation(self):
        result = run_cpu_start(ROOT, "m5.large")

        self.assertNotEqual(result.process.returncode, 0)
        self.assertIn("CPU instance identity validation failed", result.process.stderr)
        self.assertTrue(
            any("InstanceType" in call for call in result.aws_calls),
            result.aws_calls,
        )
        self.assertFalse(
            any("start-instances" in call for call in result.aws_calls),
            result.aws_calls,
        )

    def test_stop_waits_out_pending_and_stopping_states(self):
        stop = self.read("stop-cpu.sh")
        pending = stop.index('[[ "$current_state" == "pending" ]]')
        wait_running = stop.index("ec2 wait instance-running")
        mutation = stop.index("ec2 stop-instances")
        self.assertLess(pending, wait_running)
        self.assertLess(wait_running, mutation)
        self.assertIn("ec2 wait instance-stopped", stop)

    def test_scripts_do_not_embed_credentials_or_user_data(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in AWS.glob("*.sh"))
        self.assertNotIn("--user-data", text)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY=", text)
        self.assertNotIn("AWS_ACCESS_KEY_ID=", text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", text)


if __name__ == "__main__":
    unittest.main()
