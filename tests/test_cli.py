from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openshell_lab import cli


class CliTests(unittest.TestCase):
    def test_cli_publishes_only_sanitized_json_status(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.md"
            stdout = io.StringIO()
            with patch.object(
                cli,
                "run_tool_loop",
                return_value={
                    "report_file": str(output),
                    "pull_requests": [5, 4, 3, 2, 1],
                    "tool_calls": 8,
                },
            ), redirect_stdout(stdout):
                status = cli.main(["--output", str(output)])
        self.assertEqual(0, status)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("published", payload["status"])
        self.assertEqual(5, payload["pull_request_count"])
        self.assertNotIn("report_file", payload)

    def test_cli_refuses_directory_output(self):
        with tempfile.TemporaryDirectory() as directory:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                status = cli.main(["--output", directory])
        self.assertNotEqual(0, status)
        self.assertIn("directory", stderr.getvalue())

    def test_cli_returns_nonzero_without_leaking_internal_error(self):
        stderr = io.StringIO()
        with patch.object(
            cli, "run_tool_loop", side_effect=RuntimeError("secret transport detail")
        ), redirect_stderr(stderr):
            status = cli.main(["--output", "report.md"])
        self.assertNotEqual(0, status)
        self.assertEqual('{"status":"failed"}\n', stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
