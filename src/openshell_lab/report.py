import errno
import os
from pathlib import Path
import re
import tempfile


REPORT_TITLE = "# NVIDIA/OpenShell: Last 5 Merged Pull Requests"

_CREDENTIAL_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"Authorization\s*:\s*(?:Bearer|Basic)\s+\S+", re.IGNORECASE),
)


def _markdown_table_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).replace("\\", "\\\\").replace("|", "\\|")


def _plain_line(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


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
        pull_link = f"[#{pull['number']}]({pull['url']})"
        lines.append(
            "| "
            f"{_markdown_table_cell(pull_link)} | "
            f"{_markdown_table_cell(_code_labels(pull['labels']))} | "
            f"{_markdown_table_cell(pull['milestone'] or 'none')} | "
            f"{_markdown_table_cell(_linked_items(pull['associated_issues']))} | "
            f"{_markdown_table_cell(_linked_items(pull['related_pull_requests']))} | "
            f"{_markdown_table_cell(_code_labels(pull['workstream_labels']))} |"
        )
    return "\n".join(lines) + "\n"


def validate_markdown(markdown: str, evidence: dict) -> str:
    if not isinstance(markdown, str):
        raise ValueError("report must be Markdown text")
    text = markdown.strip()
    if any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS):
        raise ValueError("report contains credential material")
    if text.split("\n", 1)[0] != REPORT_TITLE:
        raise ValueError("report has an unexpected title")
    if "\n## Executive Summary\n" not in text:
        raise ValueError("report has no executive summary")

    expected_numbers = [item["number"] for item in evidence["pull_requests"]]
    if not expected_numbers:
        raise ValueError("report evidence contains no pull requests")
    headings = [
        int(number)
        for number in re.findall(r"^## PR #([0-9]+):", text, re.MULTILINE)
    ]
    if headings != expected_numbers:
        raise ValueError(
            f"report headings {headings} do not match selected pull requests {expected_numbers}"
        )

    required_patterns = (
        r"^- URL:\s+\S+",
        r"^- Merged:\s+.+",
        r"^- Author:\s+.+",
        r"^- Labels:\s+.+",
        r"^- Associated issues:\s+.+",
        r"^### What changed\s*$",
        r"^### Larger task context\s*$",
    )
    if text.count("```") % 2:
        raise ValueError("report contains an unterminated fenced code block")
    sections = re.split(r"(?=^## PR #[0-9]+:)", text, flags=re.MULTILINE)[1:]
    for number, section in zip(expected_numbers, sections, strict=True):
        structural_text = re.sub(r"```.*?```", "", section, flags=re.DOTALL)
        missing = [
            pattern
            for pattern in required_patterns
            if not re.search(pattern, structural_text, re.MULTILINE)
        ]
        if missing:
            raise ValueError(
                f"PR #{number} section is missing required structure: {', '.join(missing)}"
            )

    normalized_sections = []
    for pull, section in zip(evidence["pull_requests"], sections, strict=True):
        labels = ", ".join(_plain_line(label) for label in pull["labels"]) or "none"
        associated_issues = ", ".join(
            f"#{item['number']} ({_plain_line(item['state'])})"
            for item in pull["associated_issues"]
        ) or "none identified"
        replacements = (
            (r"^## PR #[0-9]+:.*$", f"## PR #{pull['number']}: {_plain_line(pull['title'])}"),
            (r"^- URL:.*$", f"- URL: {_plain_line(pull['url'])}"),
            (r"^- Merged:.*$", f"- Merged: {_plain_line(pull['merged_at'])}"),
            (r"^- Author:.*$", f"- Author: {_plain_line(pull['author'])}"),
            (r"^- Labels:.*$", f"- Labels: {labels}"),
            (r"^- Associated issues:.*$", f"- Associated issues: {associated_issues}"),
        )
        for pattern, replacement in replacements:
            section = re.sub(pattern, lambda _match, value=replacement: value, section, count=1, flags=re.MULTILINE)
        normalized_sections.append(section)
    first_section = text.find(sections[0])
    normalized = text[:first_section] + "".join(normalized_sections)
    if any(pattern.search(normalized) for pattern in _CREDENTIAL_PATTERNS):
        raise ValueError("report contains credential material")
    return normalized.rstrip() + "\n"


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
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            unsupported = {errno.EINVAL, errno.ENOTSUP}
            if hasattr(errno, "EOPNOTSUPP"):
                unsupported.add(errno.EOPNOTSUPP)
            if error.errno not in unsupported:
                raise
    except BaseException:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise
