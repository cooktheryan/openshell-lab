from pathlib import Path
import unittest

from test_support.shell_lab_harness import run_gpu_profile_detector


ROOT = Path(__file__).parents[1]
AWS = ROOT / "infra" / "aws"
LAB = ROOT / "labs" / "lab5"
LAB5_README = LAB / "README.md"
EVIDENCE_INDEX = ROOT / "docs" / "evidence-index.md"


class Lab5ArtifactTests(unittest.TestCase):
    def test_gpu_lifecycle_is_guarded_and_never_terminates(self):
        combined = "\n".join(
            (AWS / name).read_text(encoding="utf-8")
            for name in ("gpu-lib.sh", "start-gpu.sh", "stop-gpu.sh")
        )
        for required in (
            "us-east-2",
            "i-0482b1eb41a016cc4",
            "g6.12xlarge",
            "ami-0cbb38e3582830ad2",
            "single-server-shell",
            "openshell-qwen36-capacity-g6-2a",
            "instance-status-ok",
        ):
            self.assertIn(required, combined)
        self.assertIn("stop-instances", combined)
        self.assertNotIn("terminate-instances", combined)

    def test_gpu_identity_uses_one_snapshot_and_exactly_one_security_group(self):
        text = (AWS / "gpu-lib.sh").read_text(encoding="utf-8")
        function = text.split("validate_gpu_instance()", 1)[1].split(
            "write_gpu_state()", 1
        )[0]
        self.assertEqual(1, function.count("describe-instances"))
        self.assertIn("length(SecurityGroups)", function)
        self.assertIn("$'\\t'wide", function)

    def test_vllm_service_uses_the_exact_qwen_topology(self):
        text = (LAB / "configure-vllm.sh").read_text(encoding="utf-8")
        for required in (
            "Qwen/Qwen3.6-27B",
            "--dtype bfloat16",
            "--tensor-parallel-size 4",
            "--max-model-len 32768",
            "--max-num-seqs $MAX_NUM_SEQS",
            "--enable-auto-tool-choice",
            "--tool-call-parser qwen3_coder",
            "--device=nvidia.com/gpu=all",
            "nvidia-ctk cdi generate",
            "systemctl --user",
        ):
            self.assertIn(required, text)
        self.assertLess(
            text.index('gpu_profile_settings=$("$LAB_DIR/detect-gpu-profile.sh")'),
            text.index("sudo nvidia-ctk cdi generate"),
        )
        service_activation = text.split(
            'sudo loginctl enable-linger "$USER"', 1
        )[1]
        self.assertIn('systemctl --user restart "$SERVICE"', service_activation)
        self.assertNotIn('systemctl --user start "$SERVICE"', service_activation)

    def test_gpu_profile_detector_selects_l4_concurrency(self):
        result = run_gpu_profile_detector(
            LAB / "detect-gpu-profile.sh", ("NVIDIA L4",) * 4
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("g6-l4 16", result.stdout.strip())

    def test_gpu_profile_detector_selects_l40s_concurrency(self):
        result = run_gpu_profile_detector(
            LAB / "detect-gpu-profile.sh", ("NVIDIA L40S",) * 4
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("g6e-l40s 256", result.stdout.strip())

    def test_gpu_profile_detector_rejects_unsupported_layouts(self):
        for gpu_names in (
            ("NVIDIA L4",) * 3,
            ("NVIDIA L4", "NVIDIA L4", "NVIDIA L40S", "NVIDIA L40S"),
            ("NVIDIA RTX PRO 6000 Blackwell Server Edition",) * 4,
        ):
            with self.subTest(gpu_names=gpu_names):
                result = run_gpu_profile_detector(
                    LAB / "detect-gpu-profile.sh", gpu_names
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("unsupported GPU topology", result.stderr)

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
            "detect-gpu-profile.sh",
            "configure-openshell.sh",
            "run.sh",
            "verify.sh",
            "README.md",
        ):
            self.assertTrue((LAB / name).is_file(), name)

    def test_gpu_run_uses_lab5_identity_and_report_forward(self):
        gpu_run = (LAB / "run.sh").read_text(encoding="utf-8")

        self.assertIn('SANDBOX="openshell-lab5"', gpu_run)
        self.assertIn("openshell sandbox create", gpu_run)
        self.assertIn("--forward 127.0.0.1:18080", gpu_run)
        self.assertIn('IMAGE="localhost/openshell-lab-agent:lab5"', gpu_run)

    def test_verifier_reads_owner_only_report_through_http(self):
        text = (LAB / "verify.sh").read_text(encoding="utf-8")
        self.assertIn("published_report=$(mktemp)", text)
        self.assertIn('"$LAB_DIR/detect-gpu-profile.sh"', text)
        self.assertIn("nvidia-ctk cdi list", text)
        self.assertIn('"--dtype","bfloat16"', text)
        self.assertIn("--max-num-seqs", text)
        self.assertNotIn('grep -F \'# NVIDIA/OpenShell\' "$REPORT"', text)

    def test_lab5_runbook_identifies_gpu_lifecycle_and_pending_acceptance(self):
        runbook = LAB5_README.read_text(encoding="utf-8")

        self.assertTrue(runbook.startswith("# Lab 5: local Qwen through vLLM"))
        for marker in (
            "On the GPU host",
            "./labs/lab5/configure-vllm.sh",
            "./labs/lab5/run.sh",
            "./labs/lab5/verify.sh",
            "openshell-lab5",
            "Lab 5 remote acceptance is pending capacity",
        ):
            self.assertIn(marker, runbook)

    def test_evidence_index_marks_absent_gpu_artifacts_as_capacity_pending(self):
        index = EVIDENCE_INDEX.read_text(encoding="utf-8")
        normalized = " ".join(index.split())

        self.assertFalse((ROOT / "evidence" / "gpu").exists())
        self.assertIn("pending GPU capacity", index)
        self.assertIn("Expected at `evidence/gpu/agent-result.json`", index)
        self.assertIn(
            "There is no current Lab 5 GPU acceptance evidence", normalized
        )

    def test_evidence_index_distinguishes_current_and_acceptance_time_addresses(self):
        index = EVIDENCE_INDEX.read_text(encoding="utf-8").lower()

        self.assertIn("current connection addresses", index)
        self.assertIn("gitignored `state/*-connection.env`", index)
        self.assertIn("acceptance-time public address", index)
        self.assertIn("`evidence/cpu/summary.txt`", index)


if __name__ == "__main__":
    unittest.main()
