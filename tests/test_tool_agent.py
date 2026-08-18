import json
from pathlib import Path
import subprocess
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
    def test_request_is_bounded_and_contains_no_provider_credentials(self):
        body = tool_agent.build_chat_request([{"role": "user", "content": "report"}])
        self.assertEqual(1800, body["max_tokens"])
        self.assertEqual(0.2, body["temperature"])
        self.assertEqual("auto", body["tool_choice"])
        self.assertEqual(4, len(body["tools"]))
        self.assertFalse({"model", "api_key", "authorization"}.intersection(body))
        self.assertEqual(
            "https://inference.local/v1/chat/completions", tool_agent.MODEL_URL
        )

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
        completed = subprocess.CompletedProcess(
            args=["curl"],
            returncode=0,
            stdout=b"x" * (tool_agent.MAX_RESPONSE_BYTES + 1),
            stderr=b"",
        )
        with patch.object(subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(ValueError, "8 MiB"):
                tool_agent._curl_json("/usr/bin/curl", "https://example.test")

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
