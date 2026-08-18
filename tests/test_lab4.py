from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
AWS = ROOT / "infra" / "aws"
LAB = ROOT / "labs" / "lab4"


class Lab4ArtifactTests(unittest.TestCase):
    def test_gpu_lifecycle_is_guarded_and_never_terminates(self):
        combined = "\n".join(
            (AWS / name).read_text(encoding="utf-8")
            for name in ("gpu-lib.sh", "start-gpu.sh", "stop-gpu.sh")
        )
        for required in (
            "us-east-2",
            "i-000d2fc821040d9e3",
            "g6e.12xlarge",
            "ami-0cbb38e3582830ad2",
            "single-server-shell",
            "openshell-qwen36-single-server",
            "instance-status-ok",
        ):
            self.assertIn(required, combined)
        self.assertIn("stop-instances", combined)
        self.assertNotIn("terminate-instances", combined)

    def test_vllm_service_uses_the_exact_qwen_topology(self):
        text = (LAB / "configure-vllm.sh").read_text(encoding="utf-8")
        for required in (
            "Qwen/Qwen3.6-27B",
            "--dtype bfloat16",
            "--tensor-parallel-size 4",
            "--max-model-len 32768",
            "--enable-auto-tool-choice",
            "--tool-call-parser qwen3_coder",
            "--device=nvidia.com/gpu=all",
            "systemctl --user",
        ):
            self.assertIn(required, text)

    def test_openshell_uses_host_local_vllm_without_a_real_secret(self):
        text = (LAB / "configure-openshell.sh").read_text(encoding="utf-8")
        self.assertIn("qwen36-local", text)
        self.assertIn("http://host.openshell.internal:8000/v1", text)
        self.assertIn("http://127.0.0.1:8000/v1/models", text)
        self.assertIn("--no-verify", text)
        self.assertNotIn("OPENAI_BASE_URL=http://127.0.0.1", text)
        self.assertNotRegex(text, r"sk-[A-Za-z0-9_-]{20,}")

    def test_lab_scripts_and_manual_exist(self):
        for name in (
            "configure-vllm.sh",
            "configure-openshell.sh",
            "run.sh",
            "verify.sh",
            "README.md",
        ):
            self.assertTrue((LAB / name).is_file(), name)

    def test_verifier_reads_owner_only_report_through_http(self):
        text = (LAB / "verify.sh").read_text(encoding="utf-8")
        self.assertIn("published_report=$(mktemp)", text)
        self.assertNotIn('grep -F \'# NVIDIA/OpenShell\' "$REPORT"', text)


if __name__ == "__main__":
    unittest.main()
