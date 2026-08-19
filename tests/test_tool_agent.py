import json
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from openshell_lab import tool_agent


def model_tool_call(call_id, name, arguments):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": arguments,
                            },
                        }
                    ],
                }
            }
        ]
    }


class ToolAgentTests(unittest.TestCase):
    def test_prompt_declares_the_exact_validated_report_contract(self):
        self.assertIn(tool_agent.REPORT_TITLE, tool_agent.SYSTEM_PROMPT)
        for required in (
            "## Executive Summary",
            "## PR #{number}: {title}",
            "- URL:",
            "- Merged:",
            "- Author:",
            "- Labels:",
            "- Associated issues:",
            "### What changed",
            "### Larger task context",
        ):
            self.assertIn(required, tool_agent.SYSTEM_PROMPT)

    def test_request_is_bounded_and_contains_no_provider_credentials(self):
        body = tool_agent.build_chat_request([{"role": "user", "content": "report"}])
        self.assertEqual(8000, body["max_completion_tokens"])
        self.assertNotIn("max_tokens", body)
        self.assertEqual(1.0, body["temperature"])
        self.assertNotIn("reasoning_effort", body)
        self.assertEqual("auto", body["tool_choice"])
        self.assertEqual(4, len(body["tools"]))
        self.assertFalse({"model", "api_key", "authorization"}.intersection(body))
        self.assertEqual(
            "https://inference.local/v1/chat/completions", tool_agent.MODEL_URL
        )

    def test_agent_rejects_an_operator_supplied_executable(self):
        with self.assertRaisesRegex(ValueError, "curl executable"):
            tool_agent.run_tool_loop(Path("report.md"), curl_bin="./curl")

    def test_dispatch_restricts_pull_inspection_to_selected_set(self):
        state = tool_agent.ToolState(Path("report.md"), "/usr/bin/curl")
        state.selected_numbers = [1, 2, 3, 4, 5]
        with self.assertRaisesRegex(ValueError, "selected merge set"):
            tool_agent.dispatch_tool("inspect_pull_request", {"number": 9}, state)

    def test_dispatch_restricts_issue_inspection_to_explicit_references(self):
        state = tool_agent.ToolState(Path("report.md"), "/usr/bin/curl")
        state.selected_pulls = [
            {"number": 5, "body": "Fixes #42 and discusses issue 43"}
        ]
        with self.assertRaisesRegex(ValueError, "explicitly referenced"):
            tool_agent.dispatch_tool("inspect_linked_issue", {"number": 43}, state)

    def test_malformed_tool_arguments_are_rejected(self):
        response = model_tool_call("call-1", "list_recent_merges", "{bad json")
        with tempfile.TemporaryDirectory() as directory, patch.object(
            tool_agent, "_curl_json", return_value=response
        ):
            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                tool_agent.run_tool_loop(Path(directory) / "report.md")

    def test_tool_call_limit_is_enforced(self):
        response = model_tool_call(
            "call-1", "list_recent_merges", json.dumps({"limit": 5})
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(
            tool_agent, "_curl_json", return_value=response
        ), patch.object(tool_agent, "dispatch_tool", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "tool call limit"):
                tool_agent.run_tool_loop(
                    Path(directory) / "report.md", max_tool_calls=1
                )

    def test_response_larger_than_eight_mib_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_curl = Path(directory) / "curl"
            fake_curl.write_text(
                "#!/usr/bin/env python3\n"
                f"import sys\nsys.stdout.buffer.write(b'x' * {tool_agent.MAX_RESPONSE_BYTES + 1})\n",
                encoding="utf-8",
            )
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)
            with self.assertRaisesRegex(ValueError, "8 MiB"):
                tool_agent._curl_json(str(fake_curl), "https://example.test")

    def test_non_utf8_json_response_is_a_controlled_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_curl = Path(directory) / "curl"
            fake_curl.write_text(
                "#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(b'\\xff')\n",
                encoding="utf-8",
            )
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                tool_agent._curl_json(str(fake_curl), "https://example.test")

    def test_request_stream_closes_if_payload_write_fails(self):
        class FailedStream:
            closed = False

            def write(self, _payload):
                raise OSError("temporary storage failed")

            def close(self):
                self.closed = True

        stream = FailedStream()
        with patch.object(tool_agent.tempfile, "TemporaryFile", return_value=stream), patch.object(
            tool_agent.subprocess, "Popen"
        ) as popen, self.assertRaisesRegex(OSError, "temporary storage"):
            tool_agent._curl_json(
                "/usr/bin/curl",
                "https://inference.local/v1/chat/completions",
                {"messages": []},
            )
        self.assertTrue(stream.closed)
        popen.assert_not_called()

    def test_model_request_body_is_sent_on_standard_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_curl = root / "curl"
            captured = root / "stdin.json"
            fake_curl.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, sys\n"
                "pathlib.Path(os.environ['CAPTURE_STDIN']).write_bytes(sys.stdin.buffer.read())\n"
                "sys.stdout.write('{}')\n",
                encoding="utf-8",
            )
            fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)
            with patch.dict("os.environ", {"CAPTURE_STDIN": str(captured)}):
                tool_agent._curl_json(
                    str(fake_curl),
                    "https://inference.local/v1/chat/completions",
                    {"messages": [{"role": "user", "content": "private prompt"}]},
                )
            self.assertEqual("private prompt", json.loads(captured.read_text())["messages"][0]["content"])

    def test_request_body_uses_seekable_input_without_a_pipe_write_deadlock(self):
        class FakeProcess:
            def __init__(self):
                self.stdout = io.BytesIO(b"{}")

            def wait(self):
                return 0

            def poll(self):
                return 0

            def kill(self):
                raise AssertionError("completed process should not be killed")

        def fake_popen(_command, *, stdin, stdout, stderr):
            del stdout, stderr
            self.assertTrue(stdin.seekable())
            self.assertEqual({"messages": []}, json.loads(stdin.read()))
            return FakeProcess()

        with patch.object(tool_agent.subprocess, "Popen", side_effect=fake_popen):
            self.assertEqual(
                {},
                tool_agent._curl_json(
                    "/usr/bin/curl",
                    "https://inference.local/v1/chat/completions",
                    {"messages": []},
                ),
            )

    def test_reselecting_merges_clears_stale_issue_state(self):
        state = tool_agent.ToolState(Path("report.md"), "/usr/bin/curl")
        state.issues[42] = {"number": 42}
        pulls = [
            {"number": number, "merged_at": f"2026-08-18T0{number}:00:00Z"}
            for number in range(1, 6)
        ]
        with patch.object(tool_agent.github_evidence, "fetch_recent_merges", return_value=pulls):
            tool_agent.dispatch_tool("list_recent_merges", {"limit": 5}, state)
        self.assertEqual({}, state.issues)

    def test_tool_result_larger_than_two_mib_is_rejected(self):
        response = model_tool_call(
            "call-1", "list_recent_merges", json.dumps({"limit": 5})
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(
            tool_agent, "_curl_json", return_value=response
        ), patch.object(
            tool_agent,
            "dispatch_tool",
            return_value={"payload": "x" * tool_agent.MAX_TOOL_RESULT_BYTES},
        ):
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                tool_agent.run_tool_loop(Path(directory) / "report.md")

    def test_invalid_report_can_be_retried_before_limit(self):
        error = ValueError("report headings do not match evidence")
        result = tool_agent.recoverable_tool_error("write_report", error, 8, 16)
        self.assertTrue(result["retry"])
        self.assertIn("headings", result["detail"])
        with self.assertRaises(ValueError):
            tool_agent.recoverable_tool_error("write_report", error, 16, 16)

    def test_success_requires_write_report_tool(self):
        response = {"choices": [{"message": {"role": "assistant", "content": "done"}}]}
        with tempfile.TemporaryDirectory() as directory, patch.object(
            tool_agent, "_curl_json", return_value=response
        ):
            with self.assertRaisesRegex(ValueError, "before calling write_report"):
                tool_agent.run_tool_loop(Path(directory) / "report.md")

    def test_successful_loop_returns_sanitized_metadata(self):
        responses = [
            model_tool_call("call-list", "list_recent_merges", '{"limit":5}'),
            model_tool_call("call-write", "write_report", '{"markdown":"valid"}'),
        ]

        def fake_dispatch(name, arguments, state):
            if name == "list_recent_merges":
                state.selected_numbers = [5, 4, 3, 2, 1]
                return {"pull_requests": state.selected_numbers}
            state.report_published = True
            return {"published": True}

        with tempfile.TemporaryDirectory() as directory, patch.object(
            tool_agent, "_curl_json", side_effect=responses
        ), patch.object(tool_agent, "dispatch_tool", side_effect=fake_dispatch):
            result = tool_agent.run_tool_loop(Path(directory) / "report.md")
        self.assertEqual([5, 4, 3, 2, 1], result["pull_requests"])
        self.assertEqual(2, result["tool_calls"])


if __name__ == "__main__":
    unittest.main()
