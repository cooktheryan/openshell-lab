from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openshell_lab import cli


class CliTests(unittest.TestCase):
    def test_cli_does_not_expose_an_executable_override(self):
        with patch.object(cli, "run_tool_loop") as run_tool_loop, self.assertRaises(
            SystemExit
        ):
            cli.main(["--output", "report.md", "--curl-bin", "./curl"])
        run_tool_loop.assert_not_called()

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
        self.assertEqual(
            {"status": "published", "pull_request_count": 5, "tool_calls": 8},
            payload,
        )

    def test_cli_refuses_directory_output(self):
        with tempfile.TemporaryDirectory() as directory:
            stderr = io.StringIO()
            stdout = io.StringIO()
            with patch.object(cli, "run_tool_loop") as run_tool_loop, redirect_stderr(
                stderr
            ), redirect_stdout(stdout):
                status = cli.main(["--output", directory])
        self.assertNotEqual(0, status)
        self.assertIn("directory", stderr.getvalue())
        self.assertEqual("", stdout.getvalue())
        run_tool_loop.assert_not_called()

    def test_cli_returns_nonzero_without_leaking_internal_error(self):
        stderr = io.StringIO()
        stdout = io.StringIO()
        with patch.object(
            cli, "run_tool_loop", side_effect=RuntimeError("secret transport detail")
        ), redirect_stderr(stderr), redirect_stdout(stdout):
            status = cli.main(["--output", "report.md"])
        self.assertNotEqual(0, status)
        self.assertEqual('{"status":"failed"}\n', stderr.getvalue())
        self.assertEqual("", stdout.getvalue())

    def test_cli_normalization_failure_is_sanitized(self):
        stderr = io.StringIO()
        with patch.object(Path, "resolve", side_effect=OSError("path detail")), redirect_stderr(
            stderr
        ):
            status = cli.main(["--output", "report.md"])
        self.assertEqual(1, status)
        self.assertEqual('{"status":"failed"}\n', stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
