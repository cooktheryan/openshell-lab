from pathlib import Path
import unittest


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

    def test_lifecycle_scripts_resolve_and_validate_before_mutation(self):
        common = self.read("lib.sh")
        stop = self.read("stop-cpu.sh")
        start = self.read("start-cpu.sh")
        describe = self.read("describe-cpu.sh")
        self.assertIn("describe-tags", common)
        self.assertIn("openshell-four-labs", common)
        for script in (start, stop, describe):
            self.assertIn("load_cpu_state", script)
            self.assertIn("validate_project_instance", script)
        self.assertIn("stop-instances", stop)
        self.assertLess(stop.index("validate_project_instance"), stop.index("stop-instances"))
        self.assertLess(start.index("validate_project_instance"), start.index("start-instances"))
        self.assertNotIn("terminate-instances", stop + start + describe)
        self.assertIn("start-instances", start)
        self.assertIn("describe-instances", describe)

    def test_scripts_do_not_embed_credentials_or_user_data(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in AWS.glob("*.sh"))
        self.assertNotIn("--user-data", text)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY=", text)
        self.assertNotIn("AWS_ACCESS_KEY_ID=", text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", text)


if __name__ == "__main__":
    unittest.main()
