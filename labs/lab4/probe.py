"""Non-UI acceptance probe for the Lab 4 managed inference route."""

import argparse
import asyncio
import json

from openshell_lab.streamlit_inference import (
    call_managed_inference,
    public_error_message,
)


DEFAULT_PROMPT = "Reply with exactly: OpenShell managed inference is working"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        response = asyncio.run(
            call_managed_inference(
                [{"role": "user", "content": args.prompt}]
            )
        )
    except Exception as error:
        result = {"status": "error", "response": public_error_message(error)}
        print(json.dumps(result, separators=(",", ":")))
        return 1

    result = {"status": "ok", "response": response}
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
