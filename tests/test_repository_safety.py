import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_support.shell_lab_harness import (
    restricted_search_path,
    run_aws_secret_scan_matrix,
    run_secret_scan_with_failing_search,
)


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "scan-secrets.sh"


class RepositorySafetyTests(unittest.TestCase):
    def test_gitignore_excludes_sensitive_artifacts(self):
        patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
        required = {
            ".env",
            ".env.*",
            "state/",
            "*.pem",
            "*.key",
            "*.db",
            "**/tls/",
            ".cache/huggingface/",
            "evidence/raw/",
        }
        self.assertTrue(required.issubset(patterns), required - patterns)

    def _scan(self, filename, content, *, path=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / filename).write_text(content, encoding="utf-8")
            return subprocess.run(
                [str(SCANNER), str(root)],
                text=True,
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "LC_ALL": "C",
                    **({"PATH": path} if path is not None else {}),
                },
            )

    def test_scanner_rejects_openai_secret_without_printing_it(self):
        secret = "sk-" + "A" * 32
        result = self._scan("unsafe.txt", f"OPENAI_API_KEY={secret}\n")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unsafe.txt", result.stdout)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_scanner_rejects_private_key_marker(self):
        result = self._scan(
            "identity.txt",
            "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nredacted\n",
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("identity.txt", result.stdout)

    def test_scanner_rejects_github_token_without_printing_it(self):
        secret = "github_pat_" + "A" * 40
        result = self._scan("unsafe.txt", f"GITHUB_TOKEN={secret}\n")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unsafe.txt", result.stdout)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_scanner_allows_unassigned_credential_variable_name(self):
        result = self._scan("safe.sh", "export OPENAI_API_KEY\nunset OPENAI_API_KEY\n")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_scanner_rejects_secret_when_ripgrep_is_unavailable(self):
        secret = "sk-" + "B" * 32
        search_path = restricted_search_path()
        self.addCleanup(shutil.rmtree, search_path)
        result = self._scan(
            "unsafe.txt",
            f"OPENAI_API_KEY={secret}\n",
            path=search_path,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unsafe.txt", result.stdout)
        self.assertNotIn("command not found", result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_scanner_fails_closed_when_search_tool_errors(self):
        result = run_secret_scan_with_failing_search(SCANNER)
        self.assertEqual(2, result.returncode)
        self.assertIn("search failed", result.stderr)
        self.assertNotIn("secret-scan: clean", result.stdout)

    def test_scanner_rejects_aws_credential_forms_in_both_search_paths(self):
        results = run_aws_secret_scan_matrix(SCANNER)

        self.assertEqual(6, len(results))
        for outcome in results:
            with self.subTest(
                search_tool=outcome.search_tool,
                credential_form=outcome.credential_form,
            ):
                process = outcome.process
                self.assertNotEqual(0, process.returncode)
                self.assertIn("unsafe.txt", process.stdout)
                self.assertNotIn(
                    outcome.value,
                    process.stdout + process.stderr,
                )


if __name__ == "__main__":
    unittest.main()
