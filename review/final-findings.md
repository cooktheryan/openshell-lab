# Final OpenCodeReview dispositions

OpenCodeReview ran with the checksum-verified local `ocr` binary and GPT-5.5.
Raw JSON remains local and gitignored under `review/ocr-*.json`.

## Implemented findings

- Made Behave step imports package-qualified and idempotent.
- Rejected writable-prefix traversal and recursively detected secret-bearing request keys.
- Asserted a numeric non-root container user with an explicit failure.
- Loaded GPU acceptance settings from executable deployment artifacts.
- Rendered associated issues in the complete report fixture and validated status values.
- Paginated GitHub pulls until the updated-time boundary proves the newest five merges.
- Restricted issue relationships to explicit relationship clauses, including multi-issue clauses.
- Sent inference request bodies over standard input and bounded both curl response paths while streaming.
- Cleared stale issue state when the merge selection changes.
- Pinned the deployed agent to `/usr/bin/curl`; the CLI exposes no executable override.
- Normalized titles and metadata from collected evidence instead of trusting model-authored fields.
- Escaped Markdown table cells, anchored report structure, expanded token detection, and rescanned the final combined report.
- Preserved original atomic-write failures and synchronized the publication directory after replacement.
- Sanitized path-normalization failures, rejected empty evidence and unbalanced fences, and handled broken request pipes.
- Published reports owner-only (`0600`) and propagated unexpected directory durability failures.
- Tightened lifecycle, CLI, secret-scanner, and report-harness regression tests.

## Deliberate dispositions

- The optional generated `features/dashboard.html` viewer findings remain deferred because it is not deployed and is outside the acceptance path. Behave is the authoritative executable Gherkin renderer.
- The sandbox request deliberately omits `model`. OpenShell's `inference.local` route injects the operator-selected provider and model, allowing the same image to use GPT-5.5 or Qwen without exposing provider configuration.
- CLI failures deliberately retain a generic machine-readable error rather than returning exception text that may contain transport or credential details.
- GitHub access remains unauthenticated by design. Passing a GitHub token into the sandbox would expand the credential surface for a public-repository demonstration; bounded pagination fails closed if the public rate limit is unavailable.

The broad scans reached their token budgets after reviewing 85 and 56 files. The follow-up source-only scans completed without budget warnings so production fixes could be reviewed independently.
