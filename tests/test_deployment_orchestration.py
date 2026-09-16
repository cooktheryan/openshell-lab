import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

from test_support.shell_lab_harness import (
    generated_runner_default_lab,
    run_cpu_lab_sequence,
)


ROOT = Path(__file__).parents[1]
DEPLOY = ROOT / "scripts" / "deploy-cpu.sh"
COLLECT = ROOT / "scripts" / "collect-evidence.sh"
COLLECT_GPU = ROOT / "scripts" / "collect-gpu-evidence.sh"
OCR = ROOT / "review" / "run-ocr.sh"
CPU_SEQUENCE = ROOT / "infra" / "remote" / "run-cpu-labs.sh"
RUNNER_INSTALLER = ROOT / "infra" / "remote" / "install-runner.sh"


class DeploymentOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in (DEPLOY, COLLECT, OCR):
            if not path.is_file():
                raise AssertionError(f"missing {path}")
        cls.deploy = DEPLOY.read_text(encoding="utf-8")
        cls.collect = COLLECT.read_text(encoding="utf-8")
        cls.collect_gpu = (
            COLLECT_GPU.read_text(encoding="utf-8")
            if COLLECT_GPU.is_file()
            else ""
        )

    def _run_gpu_collector(self, members, existing_files=None):
        self.assertTrue(COLLECT_GPU.is_file(), f"missing {COLLECT_GPU}")
        existing_files = existing_files or {"stale.txt": "prior evidence\n"}
        with tempfile.TemporaryDirectory() as temporary:
            fixture_root = Path(temporary)
            repository = fixture_root / "repository"
            (repository / "scripts").mkdir(parents=True)
            (repository / "infra" / "aws").mkdir(parents=True)
            (repository / "state").mkdir()
            (repository / "evidence" / "gpu").mkdir(parents=True)
            shutil.copy2(COLLECT_GPU, repository / "scripts")
            shutil.copy2(
                ROOT / "infra" / "aws" / "gpu-lib.sh",
                repository / "infra" / "aws",
            )
            (repository / "state" / "gpu-connection.env").write_text(
                "PUBLIC_IP=192.0.2.10\n"
                "SSH_USER=ec2-user\n"
                "SSH_KEY_PATH=/fixture/id_rsa\n",
                encoding="utf-8",
            )
            (repository / "state" / "gpu-known_hosts").write_text(
                "fixture host key\n",
                encoding="utf-8",
            )
            for name, content in existing_files.items():
                destination = repository / "evidence" / "gpu" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")

            archive = fixture_root / "gpu.tar"
            with tarfile.open(archive, "w") as output:
                for name, content, kind in members:
                    info = tarfile.TarInfo(name)
                    if kind == "file":
                        payload = content.encode("utf-8")
                        info.size = len(payload)
                        output.addfile(info, io.BytesIO(payload))
                    elif kind == "symlink":
                        info.type = tarfile.SYMTYPE
                        info.linkname = content
                        output.addfile(info)
                    elif kind == "fifo":
                        info.type = tarfile.FIFOTYPE
                        output.addfile(info)
                    else:
                        raise AssertionError(f"unsupported member type: {kind}")

            fake_bin = fixture_root / "bin"
            fake_bin.mkdir()
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "cat -- \"$FAKE_GPU_ARCHIVE\"\n",
                encoding="utf-8",
            )
            fake_ssh.chmod(0o700)
            environment = os.environ.copy()
            environment.update(
                PATH=f"{fake_bin}:{environment['PATH']}",
                FAKE_GPU_ARCHIVE=str(archive),
            )
            result = subprocess.run(
                ["bash", str(repository / "scripts" / COLLECT_GPU.name)],
                cwd=repository,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            collected = {
                path.relative_to(repository / "evidence" / "gpu").as_posix():
                path.read_text(encoding="utf-8")
                for path in (repository / "evidence" / "gpu").rglob("*")
                if path.is_file()
            }
            return result, collected

    def test_pipeline_uses_strict_failure_handling_and_required_order(self):
        self.assertIn("set -euo pipefail", self.deploy)
        markers = [
            "launch-cpu.sh",
            "wait_for_ssh",
            "rsync",
            "bootstrap-rhel10.sh",
            "configure_openai",
            "infra/remote/run-cpu-labs.sh",
            "scan-secrets.sh",
            "collect-evidence.sh",
        ]
        positions = [self.deploy.index(marker) for marker in markers]
        self.assertEqual(sorted(positions), positions)

    def test_cpu_sequence_releases_lab2_forward_before_lab3(self):
        self.assertTrue(CPU_SEQUENCE.is_file(), f"missing {CPU_SEQUENCE}")
        events = run_cpu_lab_sequence(CPU_SEQUENCE)
        self.assertLess(
            events.index("lab2-verify"),
            events.index("forward-stop:18080:openshell-lab2"),
        )
        self.assertLess(
            events.index("forward-stop:18080:openshell-lab2"),
            events.index("lab3-build"),
        )

    def test_cpu_sequence_runs_lab4_after_lab3_verification(self):
        cpu_sequence = CPU_SEQUENCE.read_text(encoding="utf-8")
        self.assertIn("./labs/lab4/build.sh", cpu_sequence)
        self.assertNotIn("./labs/lab5/", cpu_sequence)
        events = run_cpu_lab_sequence(CPU_SEQUENCE)
        self.assertIn("lab4-build", events)
        self.assertLess(events.index("lab3-verify"), events.index("lab4-build"))
        self.assertEqual(
            ["lab4-build", "lab4-run", "lab4-verify"],
            events[-3:],
        )

    def test_runner_defaults_to_lab5_when_vllm_is_active(self):
        self.assertEqual("lab5", generated_runner_default_lab(RUNNER_INSTALLER))

    def test_ssh_uses_repository_known_hosts_and_strict_checking(self):
        for expected in (
            "state/known_hosts",
            "StrictHostKeyChecking=yes",
            "UserKnownHostsFile=",
            "ssh-keyscan",
        ):
            self.assertIn(expected, self.deploy + self.collect)

    def test_rsync_excludes_secrets_state_and_large_artifacts(self):
        for excluded in (
            ".env",
            "state/",
            "*.key",
            "*.pem",
            ".venv/",
            "models/",
            "*.safetensors",
        ):
            self.assertIn(excluded, self.deploy)

    def test_credential_step_requires_environment_or_interactive_tty(self):
        self.assertIn("OPENAI_API_KEY", self.deploy)
        self.assertIn("-t 0", self.deploy)
        self.assertIn("read -r -s", self.deploy)
        self.assertIn("credential input requires a TTY", self.deploy)
        self.assertNotIn("OPENAI_API_KEY=", self.deploy)

    def test_evidence_collection_is_sanitized_and_bounded(self):
        self.assertIn("evidence/cpu", self.collect)
        self.assertIn("redact", self.collect)
        self.assertIn("sha256", self.collect)
        self.assertIn("systemctl", self.collect)
        self.assertIn("openshell", self.collect)
        self.assertNotIn("provider get", self.collect)
        self.assertNotIn("credentials", self.collect.lower())

    def test_lab4_evidence_is_archived_then_redacted_as_text(self):
        self.assertIn("tar -C evidence/cpu -cf - lab4", self.collect)
        self.assertNotIn("evidence/cpu -cf - lab5", self.collect)
        self.assertIn('redact <"$source" >"$destination"', self.collect)
        self.assertNotIn("openshell provider get", self.collect)
        self.assertNotIn("printenv", self.collect)

    def test_lab4_evidence_requires_a_complete_set_and_replaces_stale_files(self):
        for marker in (
            "expected-lab4-files.txt",
            "actual-lab4-files.txt",
            "Lab 4 evidence artifact set is incomplete or unexpected",
            ".lab4-stage.",
            ".lab4-previous.",
        ):
            self.assertIn(marker, self.collect)

    def test_gpu_evidence_collection_is_sanitized_bounded_and_atomic(self):
        for marker in (
            "StrictHostKeyChecking=yes",
            "expected-gpu-files.txt",
            "actual-gpu-files.txt",
            "agent-result.json",
            "sandbox-create.log",
            "gpus.txt",
            "policy.json",
        ):
            self.assertIn(marker, self.collect_gpu)
        self.assertNotIn("openshell provider get", self.collect_gpu)
        self.assertNotIn("printenv", self.collect_gpu)

    def test_gpu_evidence_redacts_each_file_and_replaces_stale_files(self):
        secrets = (
            "sk-" + "A" * 24,
            "AKIA" + "B" * 16,
            "Authorization: Bearer hidden-value",
            "Authorization: Basic hidden-value",
        )
        filenames = (
            "agent-result.json",
            "gpus.txt",
            "policy.json",
            "sandbox-create.log",
        )
        members = [
            (f"gpu/{name}", f"safe-{index} {secrets[index]}\n", "file")
            for index, name in enumerate(filenames)
        ]

        result, collected = self._run_gpu_collector(members)

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode)
        self.assertEqual(set(filenames), set(collected))
        for index, name in enumerate(filenames):
            self.assertIn(f"safe-{index}", collected[name])
            self.assertIn("[REDACTED]", collected[name])
            self.assertNotIn(secrets[index], collected[name])

    def test_gpu_evidence_rejects_unsafe_or_mixed_archives_without_replacement(self):
        required = [
            (f"gpu/{name}", "safe\n", "file")
            for name in (
                "agent-result.json",
                "gpus.txt",
                "policy.json",
                "sandbox-create.log",
            )
        ]
        invalid_members = {
            "absolute": required + [("/escape", "unsafe\n", "file")],
            "out of scope": required + [("other/file", "unsafe\n", "file")],
            "traversal": required + [("gpu/../escape", "unsafe\n", "file")],
            "symlink": required + [("gpu/link", "policy.json", "symlink")],
            "special file": required + [("gpu/fifo", "", "fifo")],
            "mixed set": required + [("gpu/unexpected.txt", "mixed\n", "file")],
        }
        for label, members in invalid_members.items():
            with self.subTest(label=label):
                result, collected = self._run_gpu_collector(members)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual({"stale.txt": "prior evidence\n"}, collected)

    def test_ocr_script_reviews_security_and_correctness(self):
        text = OCR.read_text(encoding="utf-8")
        self.assertIn("ocr scan", text)
        for topic in (
            "security",
            "correctness",
            "least privilege",
            "secret handling",
            "documentation accuracy",
        ):
            self.assertIn(topic, text.lower())


if __name__ == "__main__":
    unittest.main()
