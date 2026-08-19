import os
from pathlib import Path
import subprocess
import tempfile
import unittest


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

    def _scan(self, filename, content):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / filename).write_text(content, encoding="utf-8")
            return subprocess.run(
                [str(SCANNER), str(root)],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "LC_ALL": "C"},
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


if __name__ == "__main__":
    unittest.main()
