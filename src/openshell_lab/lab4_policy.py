"""Validate the effective OpenShell policy recorded by the Lab 4 verifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_READ_ONLY = {
    "/usr",
    "/lib64",
    "/etc",
    "/proc",
    "/dev/urandom",
    "/opt/openshell-lab",
}
REQUIRED_READ_WRITE = ["/tmp", "/dev/null"]


def validate_effective_policy(document: dict) -> None:
    """Reject an ineffective or broader-than-approved Lab 4 policy."""
    if document.get("status") != "effective":
        raise ValueError("Lab 4 policy is not effective")
    policy = document.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("Lab 4 effective policy is missing")

    filesystem = policy.get("filesystem_policy")
    if not isinstance(filesystem, dict):
        raise ValueError("Lab 4 filesystem policy is missing")
    if filesystem.get("include_workdir") is not False:
        raise ValueError("Lab 4 workdir is not confined")
    if filesystem.get("read_write") != REQUIRED_READ_WRITE:
        raise ValueError("Lab 4 writable paths exceed the approved runtime paths")
    read_only = filesystem.get("read_only")
    if not isinstance(read_only, list) or set(read_only) != REQUIRED_READ_ONLY:
        raise ValueError("Lab 4 read-only paths differ from the approved set")

    if policy.get("landlock", {}).get("compatibility") != "hard_requirement":
        raise ValueError("Lab 4 Landlock policy is not hard-required")
    process = policy.get("process")
    if not isinstance(process, dict):
        raise ValueError("Lab 4 process policy is missing")
    if process.get("run_as_user") != "1500" or process.get("run_as_group") != "1500":
        raise ValueError("Lab 4 process identity is not 1500:1500")

    # OpenShell 0.0.116 omits an empty network_policies map when serializing
    # the effective policy. Missing and explicit-empty both mean no ordinary
    # network grant; any populated map is rejected.
    if policy.get("network_policies", {}) != {}:
        raise ValueError("Lab 4 effective policy grants ordinary network access")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy_json", type=Path)
    args = parser.parse_args(argv)
    with args.policy_json.open(encoding="utf-8") as stream:
        document = json.load(stream)
    validate_effective_policy(document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
