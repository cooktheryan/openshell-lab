from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class RemoteInstallerTests(unittest.TestCase):
    def test_runner_is_owner_only_and_validates_deployment_files(self):
        text = (ROOT / "infra/remote/install-runner.sh").read_text(encoding="utf-8")
        self.assertIn("chmod 0700", text)
        self.assertIn('[[ -x "$runner" ]]', text)

    def test_runner_accepts_and_validates_lab5(self):
        text = (ROOT / "infra/remote/install-runner.sh").read_text(encoding="utf-8")
        self.assertIn("for lab_name in lab1 lab2 lab3 lab4 lab5", text)
        self.assertIn("lab1|lab2|lab3|lab4|lab5", text)
        self.assertIn("[lab1|lab2|lab3|lab4|lab5]", text)

    def test_openai_credential_is_cleared_on_every_exit_path(self):
        text = (ROOT / "labs/lab1/configure-openai.sh").read_text(encoding="utf-8")
        self.assertIn("trap 'unset OPENAI_API_KEY' EXIT", text)


if __name__ == "__main__":
    unittest.main()
