from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).parents[1]
LAB = ROOT / "labs" / "lab4"
POLICY_PATH = ROOT / "policies" / "lab4-streamlit.yaml"
BASE_LOCK_PATH = ROOT / "container" / "base-image.lock"
ROOT_README_PATH = ROOT / "README.md"
LAB4_README_PATH = LAB / "README.md"
WHY_IT_MATTERS_PATH = ROOT / "docs" / "openshell-why-it-matters.md"


class Lab4ArtifactTests(unittest.TestCase):
    def read_required(self, path):
        self.assertTrue(path.is_file(), f"required Lab 4 artifact is missing: {path}")
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
                "labs/lab4/requirements.txt",
                "labs/lab4/app.py",
                "labs/lab4/probe.py",
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
        self.assertIn("OpenShell Lab 4", app)
        self.assertIn("st.chat_input", app)
        self.assertIn("public_error_message", app)

    def test_build_records_commit_addressed_nonroot_image(self):
        build = self.read_required(LAB / "build.sh")
        self.assertIn("localhost/openshell-lab-streamlit:$short_sha", build)
        self.assertIn("state/lab4-image.env", build)
        self.assertIn("1500:1500", build)
        self.assertIn("labs/lab4/Containerfile", build)

    def test_run_uses_durable_loopback_forward(self):
        run = self.read_required(LAB / "run.sh")
        self.assertIn("openshell-lab4", run)
        self.assertIn('FORWARD_UNIT="openshell-lab4-forward.service"', run)
        self.assertIn("-- /usr/bin/sleep infinity", run)
        self.assertIn("--target-port 8501", run)
        self.assertIn("--local 127.0.0.1:18401", run)
        self.assertIn("systemd-run --user", run)
        self.assertNotIn("0.0.0.0:18401", run)

    def test_verifier_covers_four_layers_and_model_probe(self):
        verify = self.read_required(LAB / "verify.sh")
        for marker in (
            "probe.py",
            "example.com",
            "/opt/openshell-lab/lab4-write-denied",
            "CapBnd",
            "NoNewPrivs",
            "OPENAI_API_KEY",
            "policy.json",
        ):
            self.assertIn(marker, verify)
        self.assertNotIn("openshell provider get", verify)

    def test_verifier_requires_expected_denials_and_live_loopback_evidence(self):
        verify = self.read_required(LAB / "verify.sh")
        for marker in (
            "filesystem-write-denied",
            "namespace-denied",
            "systemctl --user show",
            "ss -H -ltn",
            "127.0.0.1:18401",
            "forward-unit.txt",
            "listener.txt",
        ):
            self.assertIn(marker, verify)
        self.assertIn('[[ "$(<"$EVIDENCE_DIR/health.txt")" == "ok" ]]', verify)

    def test_workshop_documentation_explains_the_lab4_boundary(self):
        documents = {
            "root README": self.read_required(ROOT_README_PATH),
            "Lab 4 README": self.read_required(LAB4_README_PATH),
            "why-it-matters narrative": self.read_required(WHY_IT_MATTERS_PATH),
        }
        for name, text in documents.items():
            with self.subTest(document=name):
                self.assertIn("inference.local", text)
                self.assertIn("openshell-lab4", text)
                for layer in ("Filesystem", "Network", "Process", "Provider"):
                    self.assertIn(layer, text)

        tunnel = "ssh -N -L 8501:127.0.0.1:18401"
        self.assertIn(tunnel, documents["root README"])
        self.assertIn(tunnel, documents["Lab 4 README"])

    def test_public_guidance_uses_the_cpu_first_five_lab_sequence(self):
        root_readme = self.read_required(ROOT_README_PATH)
        streamlit_runbook = self.read_required(LAB4_README_PATH)

        self.assertIn("Labs 1–4", root_readme)
        self.assertIn("Lab 5: Qwen/vLLM GPU host", root_readme)
        self.assertIn("ssh -N -L 8501:127.0.0.1:18401", root_readme)
        self.assertNotIn("Labs 1–3 and 5", root_readme)
        self.assertNotIn("openshell-lab5-forward.service", streamlit_runbook)
        self.assertIn("openshell-lab4-forward.service", streamlit_runbook)

    def test_public_lab4_guidance_contains_no_obsolete_secret_or_network_path(self):
        public_guidance = "\n".join(
            (
                self.read_required(ROOT_README_PATH),
                self.read_required(LAB4_README_PATH),
            )
        ).lower()
        for forbidden in (
            "openrouter",
            "192.168.1.101",
            "llm_api_key",
            "--env openai_api_key",
            "0.0.0.0:18401",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, public_guidance)

    def test_narrative_states_the_complete_provider_credential_boundary(self):
        narrative = self.read_required(WHY_IT_MATTERS_PATH).lower()
        self.assertIn("request omits model and credential fields", narrative)
        self.assertIn(
            "outside the image, environment, filesystem, and request body",
            narrative,
        )
        self.assertIn("source of truth", narrative)
        self.assertIn("openshell-lab", narrative)


if __name__ == "__main__":
    unittest.main()
