from datetime import datetime, timezone
import json
import re
import subprocess


REPOSITORY = "NVIDIA/OpenShell"
GITHUB_API = "https://api.github.com"
PULLS_URL = (
    f"{GITHUB_API}/repos/{REPOSITORY}/pulls"
    "?state=closed&sort=updated&direction=desc&per_page=100"
)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _curl_json(url: str, curl_bin: str = "/usr/bin/curl") -> object:
    result = subprocess.run(
        [
            curl_bin,
            "--silent",
            "--show-error",
            "--fail-with-body",
            "--location",
            "--max-time",
            "30",
            "--max-filesize",
            str(MAX_RESPONSE_BYTES),
            "--header",
            "Accept: application/vnd.github+json",
            "--header",
            "X-GitHub-Api-Version: 2022-11-28",
            "--user-agent",
            "openshell-lab-merge-reporter/1.0",
            url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if len(result.stdout.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError(f"GitHub response exceeded {MAX_RESPONSE_BYTES} bytes")
    return json.loads(result.stdout)


def collect_evidence(
    curl_bin: str = "/usr/bin/curl",
    generated_at: str | None = None,
) -> dict:
    pulls_payload = _curl_json(PULLS_URL, curl_bin)
    if not isinstance(pulls_payload, list):
        raise ValueError("GitHub pulls response must be a JSON list")
    pulls = select_recent_merges(pulls_payload)

    issue_numbers = []
    for pull in pulls:
        for number in extract_issue_numbers(pull.get("body") or "", pull["number"]):
            if number not in issue_numbers:
                issue_numbers.append(number)

    issues = {}
    for number in issue_numbers:
        payload = _curl_json(
            f"{GITHUB_API}/repos/{REPOSITORY}/issues/{number}",
            curl_bin,
        )
        if not isinstance(payload, dict):
            raise ValueError(f"GitHub issue {number} response must be a JSON object")
        issues[number] = payload
    return build_evidence(pulls, issues, generated_at=generated_at)


def select_recent_merges(pulls: list[dict], limit: int = 5) -> list[dict]:
    by_number = {}
    for pull in pulls:
        if not isinstance(pull, dict) or not pull.get("merged_at"):
            continue
        number = pull.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            continue
        current = by_number.get(number)
        if current is None or pull["merged_at"] > current["merged_at"]:
            by_number[number] = pull

    selected = sorted(
        by_number.values(),
        key=lambda pull: pull["merged_at"],
        reverse=True,
    )[:limit]
    if len(selected) != limit:
        raise ValueError(
            f"expected {limit} merged pull requests, found {len(selected)}"
        )
    return selected


def extract_issue_numbers(body: str, pr_number: int, limit: int = 5) -> list[int]:
    found = []
    for match in re.finditer(r"(?<![A-Za-z0-9_])#([1-9][0-9]*)", body or ""):
        number = int(match.group(1))
        if number != pr_number and number not in found:
            found.append(number)
        if len(found) == limit:
            break
    return found


def _label_names(item: dict) -> list[str]:
    return [
        label["name"]
        for label in item.get("labels", [])
        if isinstance(label, dict) and isinstance(label.get("name"), str)
    ]


def _related_item(issue: dict) -> dict:
    number = issue["number"]
    return {
        "number": number,
        "title": issue.get("title") or "",
        "state": issue.get("state") or "unknown",
        "labels": _label_names(issue),
        "url": issue.get("html_url")
        or f"https://github.com/{REPOSITORY}/issues/{number}",
    }


def build_evidence(
    pulls: list[dict],
    issues: dict[int, dict],
    generated_at: str | None = None,
) -> dict:
    if generated_at is None:
        generated_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    normalized = []
    for pull in pulls:
        associated_issues = []
        related_pull_requests = []
        for number in extract_issue_numbers(pull.get("body") or "", pull["number"]):
            issue = issues.get(number)
            if issue is None:
                continue
            target = related_pull_requests if issue.get("pull_request") else associated_issues
            target.append(_related_item(issue))

        labels = _label_names(pull)
        normalized.append(
            {
                "number": pull["number"],
                "title": pull.get("title") or "",
                "url": pull.get("html_url")
                or f"https://github.com/{REPOSITORY}/pull/{pull['number']}",
                "merged_at": pull["merged_at"],
                "author": (pull.get("user") or {}).get("login") or "unknown",
                "labels": labels,
                "workstream_labels": [
                    label
                    for label in labels
                    if label.startswith(
                        ("area:", "topic:", "os:", "component:", "platform:")
                    )
                ],
                "milestone": (pull.get("milestone") or {}).get("title"),
                "body": (pull.get("body") or "")[:4000],
                "associated_issues": associated_issues,
                "related_pull_requests": related_pull_requests,
            }
        )

    return {
        "repository": REPOSITORY,
        "repository_url": f"https://github.com/{REPOSITORY}",
        "generated_at": generated_at,
        "pull_requests": normalized,
    }
