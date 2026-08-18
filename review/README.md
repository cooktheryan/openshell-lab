# OpenCodeReview gates

`run-ocr.sh` verifies the installed OpenCodeReview binary against `ocr.lock`
before scanning. It reviews security, correctness, policy least privilege,
secret handling, failure behavior, and documentation accuracy with GPT-5.5.

Run from the repository root with `OPENAI_API_KEY` already exported:

```shell
./review/run-ocr.sh
```

The raw JSON result remains local as `review/ocr-cpu.json`. Findings are
reproduced and dispositioned in `cpu-findings.md`; a review suggestion is never
implemented solely because the model proposed it.
