"""Bounded OpenAI-compatible tool loop for the merge-report lab."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess

from openshell_lab import github_evidence
from openshell_lab.report import (
    REPORT_TITLE,
    render_evidence_index,
    validate_markdown,
    write_report,
)


MODEL_URL = "https://inference.local/v1/chat/completions"
MAX_TOOL_CALLS = 16
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_TOOL_RESULT_BYTES = 2 * 1024 * 1024

SYSTEM_PROMPT = """You are a release-analysis agent operating behind OpenShell.
Create an evidence-grounded Markdown report for exactly the five most recently
merged NVIDIA/OpenShell pull requests. Begin by calling list_recent_merges.
Inspect selected pull requests as needed. Inspect only issues explicitly linked
from selected pull request bodies. Finish by calling write_report. Never invent
labels, issues, milestones, or larger-task relationships. Classify work as part
of a larger task only when an issue, meaningful label, milestone, or explicit
body relationship provides evidence.


The Markdown passed to write_report MUST follow this exact contract:
# NVIDIA/OpenShell: Last 5 Merged Pull Requests
## Executive Summary
## PR #{number}: {title}
- URL:
- Merged:
- Author:
- Labels:
- Associated issues:
### What changed
### Larger task context

Repeat the PR section exactly once for each selected pull request, in the order
returned by list_recent_merges. Do not add text before the exact report title."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_recent_merges",
            "description": "List exactly the five latest NVIDIA/OpenShell merges.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "enum": [5]}},
                "required": ["limit"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_pull_request",
            "description": "Inspect one pull request from the selected merge set.",
            "parameters": {
                "type": "object",
                "properties": {"number": {"type": "integer", "minimum": 1}},
                "required": ["number"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_linked_issue",
            "description": "Inspect an issue explicitly linked from a selected PR.",
            "parameters": {
                "type": "object",
                "properties": {"number": {"type": "integer", "minimum": 1}},
                "required": ["number"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_report",
            "description": (
                "Validate and publish the Markdown report with an Executive Summary "
                "and one ordered section for every selected pull request."
            ),
            "parameters": {
                "type": "object",
                "properties": {"markdown": {"type": "string", "minLength": 200}},
                "required": ["markdown"],
                "additionalProperties": False,
            },
        },
    },
]


@dataclass
class ToolState:
    report_path: Path | str
    curl_bin: str
    selected_pulls: list[dict] = field(default_factory=list)
    selected_numbers: list[int] = field(default_factory=list)
    issues: dict[int, dict] = field(default_factory=dict)
    report_published: bool = False

    def __post_init__(self):
        self.report_path = Path(self.report_path)


def build_chat_request(messages: list[dict]) -> dict:
    # OpenShell's inference.local route injects the operator-selected provider model.
    # Keeping it out of the sandbox request lets the same image use GPT-5.5 or Qwen.
    return {
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 1.0,
        "max_completion_tokens": 8000,
    }


def enforce_call_limit(call_count: int, maximum: int = MAX_TOOL_CALLS) -> None:
    if call_count > maximum:
        raise RuntimeError(f"tool call limit exceeded: {call_count} > {maximum}")


def recoverable_tool_error(
    name: str,
    error: ValueError,
    call_count: int,
    maximum: int = MAX_TOOL_CALLS,
) -> dict:
    if name != "write_report" or call_count >= maximum:
        raise error
    return {
        "error": "write_report validation failed",
        "detail": str(error)[:500],
        "retry": True,
    }


def compact_pull(pull: dict, body_limit: int = 4000) -> dict:
    return {
        "number": pull["number"],
        "title": pull.get("title") or "",
        "body": (pull.get("body") or "")[:body_limit],
        "merged_at": pull.get("merged_at"),
        "url": pull.get("html_url"),
        "labels": [
            label["name"]
            for label in pull.get("labels", [])
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        ],
        "milestone": (pull.get("milestone") or {}).get("title"),
        "author": (pull.get("user") or {}).get("login"),
    }


def compact_issue(issue: dict) -> dict:
    return {
        "number": issue["number"],
        "title": issue.get("title") or "",
        "state": issue.get("state") or "unknown",
        "url": issue.get("html_url"),
        "labels": [
            label["name"]
            for label in issue.get("labels", [])
            if isinstance(label, dict) and isinstance(label.get("name"), str)
        ],
        "is_pull_request": bool(issue.get("pull_request")),
    }


def _positive_number(arguments: dict) -> int:
    if set(arguments) != {"number"}:
        raise ValueError("tool arguments must contain only number")
    number = arguments["number"]
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("number must be a positive integer")
    return number


def _curl_json(curl_bin: str, url: str, request_body: dict | None = None) -> object:
    command = [
        curl_bin,
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--max-time",
        "180" if request_body is not None else "30",
        "--max-filesize",
        str(MAX_RESPONSE_BYTES),
    ]
    if request_body is None:
        command.extend(
            [
                "--header",
                "Accept: application/vnd.github+json",
                "--header",
                "X-GitHub-Api-Version: 2022-11-28",
                "--user-agent",
                "openshell-lab-merge-reporter/1.0",
            ]
        )
    else:
        request_payload = json.dumps(request_body, separators=(",", ":")).encode(
            "utf-8"
        )
        command.extend(
            [
                "--request",
                "POST",
                "--header",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
            ]
        )
    command.append(url)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if request_body is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    chunks = []
    try:
        if request_body is not None:
            try:
                process.stdin.write(request_payload)
            except BrokenPipeError:
                pass
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
        total = 0
        while True:
            chunk = process.stdout.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("response exceeds 8 MiB limit")
            chunks.append(chunk)
        returncode = process.wait()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
    response_body = b"".join(chunks)
    if returncode != 0:
        detail = response_body.decode("utf-8", "replace")[:500]
        raise RuntimeError(f"curl failed with status {returncode}: {detail}")
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON response from {url}") from error


def _allowed_issue_numbers(state: ToolState) -> set[int]:
    allowed = set()
    for pull in state.selected_pulls:
        allowed.update(
            github_evidence.extract_issue_numbers(
                pull.get("body") or "", pull["number"]
            )
        )
    return allowed


def dispatch_tool(name: str, arguments: dict, state: ToolState) -> dict:
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    if name == "list_recent_merges":
        if arguments != {"limit": 5}:
            raise ValueError("list_recent_merges requires limit 5")
        state.selected_pulls = github_evidence.fetch_recent_merges(state.curl_bin)
        state.selected_numbers = [pull["number"] for pull in state.selected_pulls]
        state.issues.clear()
        return {
            "repository": github_evidence.REPOSITORY,
            "pull_requests": [compact_pull(pull, 500) for pull in state.selected_pulls],
        }
    if name == "inspect_pull_request":
        number = _positive_number(arguments)
        if number not in state.selected_numbers:
            raise ValueError("pull request is not in the selected merge set")
        pull = _curl_json(
            state.curl_bin,
            f"{github_evidence.GITHUB_API}/repos/{github_evidence.REPOSITORY}/pulls/{number}",
        )
        if not isinstance(pull, dict):
            raise ValueError("GitHub pull response must be an object")
        state.selected_pulls[state.selected_numbers.index(number)] = pull
        return compact_pull(pull)
    if name == "inspect_linked_issue":
        number = _positive_number(arguments)
        if number not in _allowed_issue_numbers(state):
            raise ValueError(
                "issue is not explicitly referenced by a selected pull request"
            )
        issue = _curl_json(
            state.curl_bin,
            f"{github_evidence.GITHUB_API}/repos/{github_evidence.REPOSITORY}/issues/{number}",
        )
        if not isinstance(issue, dict):
            raise ValueError("GitHub issue response must be an object")
        state.issues[number] = issue
        return compact_issue(issue)
    if name == "write_report":
        if set(arguments) != {"markdown"} or not isinstance(
            arguments["markdown"], str
        ):
            raise ValueError("write_report requires only a Markdown string")
        if len(state.selected_numbers) != 5:
            raise ValueError("five merged pull requests must be selected before publication")
        evidence = github_evidence.build_evidence(state.selected_pulls, state.issues)
        markdown = validate_markdown(arguments["markdown"], evidence)
        markdown = markdown.rstrip() + "\n\n" + render_evidence_index(evidence)
        markdown = validate_markdown(markdown, evidence)
        write_report(state.report_path, markdown)
        state.report_published = True
        return {"published": True, "path": str(state.report_path)}
    raise ValueError(f"unsupported tool: {name}")


def _assistant_message(payload: object) -> dict:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("chat response contains no assistant message") from error
    if not isinstance(message, dict):
        raise ValueError("assistant message must be an object")
    return message


def run_tool_loop(
    report_path: Path,
    curl_bin: str = "/usr/bin/curl",
    max_tool_calls: int = MAX_TOOL_CALLS,
) -> dict:
    if curl_bin != "/usr/bin/curl":
        raise ValueError("unsupported curl executable; expected /usr/bin/curl")
    state = ToolState(report_path, curl_bin)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Analyze the five latest merged pull requests and publish the report.",
        },
    ]
    call_count = 0
    while True:
        response = _curl_json(curl_bin, MODEL_URL, build_chat_request(messages))
        message = _assistant_message(response)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            raise ValueError("model completed before calling write_report")
        messages.append(
            {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": tool_calls,
            }
        )
        for tool_call in tool_calls:
            call_count += 1
            enforce_call_limit(call_count, max_tool_calls)
            if not isinstance(tool_call, dict) or not isinstance(
                tool_call.get("function"), dict
            ):
                raise ValueError("malformed tool call")
            call_id = tool_call.get("id")
            function = tool_call["function"]
            name = function.get("name")
            if not isinstance(call_id, str) or not call_id or not isinstance(name, str):
                raise ValueError("malformed tool call identity")
            try:
                arguments = json.loads(function.get("arguments"))
            except (TypeError, json.JSONDecodeError) as error:
                raise ValueError("tool arguments are not valid JSON") from error
            try:
                result = dispatch_tool(name, arguments, state)
            except ValueError as error:
                result = recoverable_tool_error(
                    name, error, call_count, max_tool_calls
                )
            if state.report_published:
                return {
                    "report_file": str(state.report_path),
                    "pull_requests": state.selected_numbers,
                    "associated_issue_count": sum(
                        1
                        for issue in state.issues.values()
                        if not issue.get("pull_request")
                    ),
                    "tool_calls": call_count,
                }
            serialized = json.dumps(result, separators=(",", ":"), sort_keys=True)
            if len(serialized.encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
                raise ValueError("tool result exceeds 2 MiB limit")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": serialized,
                }
            )
