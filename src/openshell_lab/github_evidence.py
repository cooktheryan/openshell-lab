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
MAX_PULL_PAGES = 10


def _parse_github_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"GitHub {field} is not a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"GitHub {field} is not a valid timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"GitHub {field} has no timezone")
    return parsed.astimezone(timezone.utc)


def _curl_json(url: str, curl_bin: str = "/usr/bin/curl") -> object:
    process = subprocess.Popen(
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
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    chunks = []
    try:
        total = 0
        while True:
            chunk = process.stdout.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError(f"GitHub response exceeded {MAX_RESPONSE_BYTES} bytes")
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
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid GitHub JSON response from {url}") from error


def collect_evidence(
    curl_bin: str = "/usr/bin/curl",
    generated_at: str | None = None,
) -> dict:
    pulls = fetch_recent_merges(curl_bin)

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


def fetch_recent_merges(curl_bin: str = "/usr/bin/curl") -> list[dict]:
    """Fetch enough updated-time-ordered pages to prove the latest five merges."""
    collected = []
    for page_number in range(1, MAX_PULL_PAGES + 1):
        page = _curl_json(f"{PULLS_URL}&page={page_number}", curl_bin)
        if not isinstance(page, list):
            raise ValueError("GitHub pulls response must be a JSON list")
        collected.extend(page)
        try:
            selected = select_recent_merges(collected)
        except ValueError:
            if len(page) < 100:
                raise
            continue
        if len(page) < 100:
            return selected
        try:
            tail_updated_at = _parse_github_timestamp(
                page[-1].get("updated_at") if page else None,
                "updated-time pagination boundary",
            )
            cutoff = _parse_github_timestamp(
                selected[-1]["merged_at"],
                "merge cutoff",
            )
        except ValueError as error:
            raise ValueError(
                "GitHub pull page has an invalid updated-time pagination boundary"
            ) from error
        if tail_updated_at <= cutoff:
            return selected
    raise ValueError(
        f"could not prove the latest five merges within {MAX_PULL_PAGES} GitHub pages"
    )


def select_recent_merges(pulls: list[dict], limit: int = 5) -> list[dict]:
    by_number = {}
    for pull in pulls:
        if not isinstance(pull, dict):
            continue
        merged_at = pull.get("merged_at")
        if not isinstance(merged_at, str):
            continue
        try:
            merged_time = _parse_github_timestamp(merged_at, "merge timestamp")
        except ValueError:
            continue
        number = pull.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            continue
        current = by_number.get(number)
        if current is None or merged_time > current[1]:
            by_number[number] = (pull, merged_time)

    selected = [
        pull
        for pull, _merged_time in sorted(
            by_number.values(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]
    ]
    if len(selected) != limit:
        raise ValueError(
            f"expected {limit} merged pull requests, found {len(selected)}"
        )
    return selected


_RELATIONSHIP = re.compile(
    r"(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?|relate[sd]?(?:\s+to)?|part\s+of|"
    r"follows?|follow-up\s+to|depends\s+on|blocked\s+by)\s*:?\s*$",
    re.IGNORECASE,
)
_NEGATED_RELATIONSHIP = re.compile(
    r"(?:does\s+not|did\s+not|not)\s+"
    r"(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?|relate[sd]?(?:\s+to)?|part\s+of|"
    r"follows?|follow-up\s+to|depends?\s+on|blocked\s+by)\s*:?\s*$",
    re.IGNORECASE,
)
_ISSUE_REFERENCE = re.compile(
    r"(?:"
    r"(?<![A-Za-z0-9_/])(?:(?:NVIDIA/OpenShell)#|#)"
    r"|https://github\.com/NVIDIA/OpenShell/(?:issues|pull)/"
    r")([1-9][0-9]*)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def extract_issue_numbers(body: str, pr_number: int, limit: int = 5) -> list[int]:
    found = []
    previous_end = None
    relationship_clause = False
    for match in _ISSUE_REFERENCE.finditer(body or ""):
        prefix = (body or "")[max(0, match.start() - 80) : match.start()]
        if _NEGATED_RELATIONSHIP.search(prefix):
            relationship_clause = False
        elif _RELATIONSHIP.search(prefix):
            relationship_clause = True
        elif previous_end is None or not relationship_clause or not re.fullmatch(
            r"\s*(?:(?:,|and|&)\s*)+", (body or "")[previous_end : match.start()], re.IGNORECASE
        ):
            relationship_clause = False
        previous_end = match.end()
        if not relationship_clause:
            continue
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
    number = issue.get("number") if isinstance(issue, dict) else None
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("GitHub issue payload has no valid issue number")
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
