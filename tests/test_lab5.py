from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).parents[1]
LAB = ROOT / "labs" / "lab5"
POLICY_PATH = ROOT / "policies" / "lab5-streamlit.yaml"
BASE_LOCK_PATH = ROOT / "container" / "base-image.lock"


class Lab5ArtifactTests(unittest.TestCase):
    def read_required(self, path):
        self.assertTrue(path.is_file(), f"required Lab 5 artifact is missing: {path}")
        return path.read_text(encoding="utf-8")

    def test_policy_is_hard_required_and_default_deny(self):
        policy = yaml.safe_load(self.read_required(POLICY_PATH))

        self.assertEqual("hard_requirement", policy["landlock"]["compatibility"])
        self.assertEqual({}, policy["network_policies"])
        self.assertEqual("1500", policy["process"]["run_as_user"])
        self.assertEqual("1500", policy["process"]["run_as_group"])
        self.assertFalse(policy["filesystem_policy"]["include_workdir"])
        self.assertEqual(
            ["/tmp", "/dev/null"], policy["filesystem_policy"]["read_write"]
        )
        self.assertEqual(
            ["/usr", "/lib64", "/etc", "/proc", "/dev/urandom", "/opt/openshell-lab"],
            policy["filesystem_policy"]["read_only"],
        )

    def test_container_is_nonroot_keyless_and_uses_managed_inference(self):
        containerfile = self.read_required(LAB / "Containerfile")
        app = self.read_required(LAB / "app.py")

        self.assertIn("USER 1500:1500", containerfile)
        self.assertIn('"streamlit", "run", "app.py"', containerfile)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", containerfile)
        self.assertIn("call_managed_inference", app)
        self.assertNotIn("OPENAI_API_KEY", containerfile + app)
        self.assertNotIn("Authorization", containerfile + app)
        self.assertNotIn("openrouter", (containerfile + app).lower())

    def test_container_uses_locked_base_and_bounded_copy_sources(self):
        containerfile = self.read_required(LAB / "Containerfile")
        lock = dict(
            line.split("=", 1)
            for line in self.read_required(BASE_LOCK_PATH).splitlines()
            if "=" in line
        )
        expected_base = f'{lock["name"]}@{lock["digest"]}'

        self.assertIn(f"FROM {expected_base}", containerfile)
        self.assertIn("HOME=/tmp/streamlit-home", containerfile)
        self.assertIn("EXPOSE 8501", containerfile)
        copy_sources = []
        for line in containerfile.splitlines():
            if line.startswith("COPY "):
                without_options = re.sub(r"^COPY(?:\s+--\S+)*\s+", "", line)
                copy_sources.append(without_options.split()[0])
        self.assertEqual(
            [
                "labs/lab5/requirements.txt",
                "labs/lab5/app.py",
                "labs/lab5/probe.py",
                "src/openshell_lab/__init__.py",
                "src/openshell_lab/streamlit_inference.py",
            ],
            copy_sources,
        )
        forbidden_fragments = (".env", ".key", "credential", "192.168.", "10.0.")
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, "\n".join(copy_sources).lower())

    def test_runtime_dependencies_are_exactly_pinned(self):
        requirements = self.read_required(LAB / "requirements.txt").splitlines()
        self.assertEqual(["streamlit==1.41.1", "httpx==0.28.1"], requirements)

    def test_probe_uses_the_shared_client_and_sanitized_failures(self):
        probe = self.read_required(LAB / "probe.py")
        self.assertIn("call_managed_inference", probe)
        self.assertIn("public_error_message", probe)
        self.assertNotIn("os.environ", probe)
        self.assertNotIn("traceback", probe)

    def test_application_presents_all_four_control_layers(self):
        app = self.read_required(LAB / "app.py")
        for layer in ("Filesystem", "Network", "Process", "Provider"):
            self.assertIn(layer, app)
        self.assertIn("OpenShell Lab 5", app)
        self.assertIn("st.chat_input", app)
        self.assertIn("public_error_message", app)


if __name__ == "__main__":
    unittest.main()
