import os
from pathlib import Path
import re
import tempfile


REPORT_TITLE = "# NVIDIA/OpenShell: Last 5 Merged Pull Requests"

_CREDENTIAL_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"Authorization\s*:\s*(?:Bearer|Basic)\s+\S+", re.IGNORECASE),
)


def _code_labels(labels: list[str]) -> str:
    return ", ".join(f"`{label}`" for label in labels) or "none"


def _linked_items(items: list[dict]) -> str:
    rendered = []
    for item in items:
        rendered.append(
            f"[#{item['number']}]({item['url']}) "
            f"({item['state']}; labels: {_code_labels(item['labels'])})"
        )
    return "; ".join(rendered) or "none"


def render_evidence_index(evidence: dict) -> str:
    lines = [
        "## Evidence Index",
        "",
        "This index is rendered deterministically from GitHub API fields.",
        "",
        "| Pull request | PR labels | Milestone | Associated issues | Related pull requests | Workstream labels |",
        "|---|---|---|---|---|---|",
    ]
    for pull in evidence["pull_requests"]:
        lines.append(
            "| "
            f"[#{pull['number']}]({pull['url']}) | "
            f"{_code_labels(pull['labels'])} | "
            f"{pull['milestone'] or 'none'} | "
            f"{_linked_items(pull['associated_issues'])} | "
            f"{_linked_items(pull['related_pull_requests'])} | "
            f"{_code_labels(pull['workstream_labels'])} |"
        )
    return "\n".join(lines) + "\n"


def validate_markdown(markdown: str, evidence: dict) -> str:
    if not isinstance(markdown, str):
        raise ValueError("report must be Markdown text")
    text = markdown.strip()
    if any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS):
        raise ValueError("report contains credential material")
    if not text.startswith(REPORT_TITLE):
        raise ValueError("report has an unexpected title")
    if "\n## Executive Summary\n" not in text:
        raise ValueError("report has no executive summary")

    expected_numbers = [item["number"] for item in evidence["pull_requests"]]
    headings = [
        int(number)
        for number in re.findall(r"^## PR #([0-9]+):", text, re.MULTILINE)
    ]
    if headings != expected_numbers:
        raise ValueError(
            f"report headings {headings} do not match selected pull requests {expected_numbers}"
        )

    required_fields = (
        "- URL:",
        "- Merged:",
        "- Author:",
        "- Labels:",
        "- Associated issues:",
        "### What changed",
        "### Larger task context",
    )
    sections = re.split(r"(?=^## PR #[0-9]+:)", text, flags=re.MULTILINE)[1:]
    for number, section in zip(expected_numbers, sections, strict=True):
        missing = [field for field in required_fields if field not in section]
        if missing:
            raise ValueError(f"PR #{number} section is missing: {', '.join(missing)}")
    return text + "\n"


def write_report(path: Path | str, markdown: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f"{destination.name}.",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(markdown)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, destination)
    except BaseException:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        raise
