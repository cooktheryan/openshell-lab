"""Command-line entry point for the bounded merge-report agent."""

import argparse
import json
from pathlib import Path
import sys

from openshell_lab.tool_agent import run_tool_loop


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openshell-lab-report")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--curl-bin", default="/usr/bin/curl")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    output = arguments.output.expanduser().resolve()
    if output.is_dir():
        print("output path is a directory", file=sys.stderr)
        return 2
    try:
        result = run_tool_loop(output, curl_bin=arguments.curl_bin)
    except (OSError, RuntimeError, ValueError):
        print('{"status":"failed"}', file=sys.stderr)
        return 1
    status = {
        "status": "published",
        "pull_request_count": len(result["pull_requests"]),
        "tool_calls": result["tool_calls"],
    }
    print(json.dumps(status, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
