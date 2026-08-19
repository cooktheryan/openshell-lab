# Final OpenCodeReview dispositions

OpenCodeReview ran with the checksum-verified local `ocr` binary and GPT-5.5.
Raw JSON remains local and gitignored under `review/ocr-*.json`.

## Implemented findings

- Resolved the latest stable NVIDIA/OpenShell release, fetched the installer
  from that immutable release tag, and verified the installed CLI version.
- Serialized CPU launches, persisted provisional instance identity before
  health waits, validated lifecycle state fields, and handled pending/stopping
  transitions explicitly.
- Validated GPU identity from one EC2 snapshot and required exactly one approved
  security group; shell-escaped sourceable state and scoped restrictive umasks.
- Fixed Lab 3 stale-forward cleanup, removed partial denied output, and required
  exactly five PR sections in the served report.
- Made the installed home-directory runner owner-only, validated every lab
  entrypoint, and cleared OpenAI credentials on every configuration exit path.
- Paginated all active Quay tags, retained the stable immutable base-image
  digest, and cleaned temporary resolver artifacts on failure.
- Rejected fenced-heading spoofing, duplicate/unapproved report sections, and
  model-authored evidence indexes before deterministic publication.
- Recognized colon-form and full-URL GitHub issue relationships while retaining
  negation handling.
- Parsed GitHub merge and pagination timestamps as timezone-aware UTC values,
  rejected malformed boundaries, and ordered offset timestamps chronologically.
- Made atomic publication skip unsupported Windows directory fsync while
  retaining durability-error propagation on supported POSIX filesystems.
- Distinguished writable device files from directory roots and hardened the
  managed-request credential detector against aliases and bearer values.
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
- The read-only `/etc` and `/proc` paths and writable `/tmp` and `/dev/null`
  entries are OpenShell's observed runtime baseline. `/var/www/html` is confined
  by the Podman driver to the dedicated host subtree
  `/var/www/html/openshell-lab`; the evidence files record effective policy and
  are not hand-edited into an aspirational shape.
- Lab 2's user-wide bind-mount driver capability and Apache SELinux boolean are
  explicit single-server workshop prerequisites. The lab validates the one
  reviewed mount at runtime; production multi-tenant deployments should use a
  separately scoped gateway rather than reuse this profile.
- `configure-openshell.sh --no-verify` is limited to the already-probed,
  host-local vLLM endpoint. No provider credential crosses into the sandbox.

The full-filesystem review was continued across multiple token-budget windows;
raw review sessions remain gitignored. A focused post-fix scan and the complete
local verification gate provide the final acceptance evidence. The final
source-validation scans completed successfully without scan warnings; every
reported source finding was reproduced, regression-tested, and fixed.
