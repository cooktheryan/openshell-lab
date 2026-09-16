# OpenShell Lab 5 Streamlit Design

> **Numbering note:** This is a historical implementation record. The current
> workshop numbering is defined by
> `docs/superpowers/specs/2026-09-16-renumber-streamlit-lab4-gpu-lab5-design.md`:
> Streamlit is Lab 4 and GPU Qwen is Lab 5.

## Purpose

Lab 5 adds a browser-based Streamlit application to the existing OpenShell
workshop. It demonstrates that a containerized application can use GPT-5.5
through OpenShell's managed inference proxy without receiving the provider
hostname, selected model, API key, or authorization header.

The lab migrates the useful Streamlit application and security narrative from
`~/git/blog` into `openshell-lab`. It does not modify or delete the source blog
repository or its untracked Word document.

## Workshop Progression

Labs 1 through 3 establish managed inference, progressively constrained
filesystem access, a non-root application image, and deny-to-allow policy
iteration. Lab 4 substitutes local Qwen inference on the GPU host. Lab 5 returns
to the Labs 1 through 3 CPU host and presents managed inference through a web
application running inside an OpenShell sandbox.

The Lab 5 lesson is not that a plain container is deliberately vulnerable. The
lesson is that a non-root container is a sound baseline while OpenShell adds
four agent-specific control layers:

1. Filesystem access constrained by Landlock.
2. Process identity and privilege reduction.
3. Default-deny ordinary network egress.
4. Provider-bound model access through `inference.local` without application
   credentials.

## Deployment Boundary

Lab 5 runs on the guarded RHEL CPU instance used by Labs 1 through 3. It reuses
the `openai-gpt55` provider and GPT-5.5 inference selection configured by
`labs/lab1/configure-openai.sh`.

There is one application deployment: a non-root Streamlit image inside an
OpenShell sandbox named `openshell-lab5`. The earlier blog's plain-container and
OpenRouter deployments are not carried forward because they conflict with the
credential-free managed-inference boundary.

Streamlit listens on port 8501 inside the sandbox. A durable OpenShell service
forward binds only to host loopback port 18501. Operators reach it through an
SSH tunnel that maps local port 8501 to host port 18501. Lab automation does not
bind Streamlit to a public interface.

## Components

### Streamlit application

The application provides a small chat interface and an explanation of the
active OpenShell controls. It accepts a bounded user prompt, retains a bounded
conversation history in Streamlit session state, calls managed inference, and
renders the assistant response.

The UI contains no tool-execution feature. Filesystem, network, process, and
provider controls are demonstrated by the verification script rather than by
giving arbitrary shell execution to a browser user.

### Managed inference client

A framework-independent Python module owns request construction, response
validation, and limits. Its fixed endpoint is:

```text
https://inference.local/v1/chat/completions
```

The request body contains messages and bounded generation settings. It omits
the model and all credential-bearing fields. The client sends no Authorization
header. OpenShell selects GPT-5.5 and injects provider credentials after policy
admits the inference request.

The client limits individual prompts to 4,000 characters, retains at most 20
conversation messages, uses a 180-second request timeout, and rejects responses
larger than 1 MiB. These limits prevent browser sessions from creating
unbounded proxy requests or memory growth.

### Container image

Lab 5 has a dedicated Containerfile built from the repository root. It installs
pinned Streamlit and HTTP client dependencies, copies only the Lab 5
application and inference client, declares a numeric `USER 1500:1500`, and
starts Streamlit on `0.0.0.0:8501` inside the sandbox network namespace.

The image uses `/opt/openshell-lab` as its read-only application directory.
Runtime home, cache, and Streamlit state are redirected beneath `/tmp`.

The build script tags the image with the current Git revision and records the
image identity in a gitignored state file, following the Lab 3 pattern.

### OpenShell policy

The Lab 5 policy:

- exposes application code and required system paths as read-only;
- permits writes only to `/tmp` and `/dev/null`;
- uses Landlock `hard_requirement`;
- runs the application as UID and GID 1500;
- declares no ordinary network policy.

Managed `inference.local` traffic remains available through OpenShell's
separate inference route. Requests to undeclared internet hosts remain denied.

### Lifecycle scripts

`build.sh` builds and records the immutable image identity.

`run.sh` removes any previous Lab 5 sandbox and forward, creates the sandbox
from the recorded image and Lab 5 policy, starts the Streamlit process, waits
for its internal health endpoint, and creates the durable loopback service
forward. The script returns after readiness and leaves the sandbox and forward
running for inspection.

`verify.sh` confirms application readiness and every security acceptance
condition. Cleanup remains explicit so learners can inspect the running lab.

## Data Flow

1. The operator establishes an SSH tunnel from local port 8501 to the CPU
   host's loopback port 18501.
2. The browser sends a prompt to Streamlit through that tunnel and OpenShell
   service forward.
3. Streamlit passes bounded conversation messages to the inference client.
4. The client posts a credential-free request to `inference.local`.
5. OpenShell routes the request through the configured `openai-gpt55` provider,
   supplies GPT-5.5 and its credential outside the application, and returns the
   model response.
6. Streamlit renders validated assistant text in the browser session.

No model credential crosses the SSH tunnel, enters the image, appears in the
application environment, or becomes part of the request body.

## Error Handling

The inference client rejects empty or oversized prompts before making a
request. It rejects malformed JSON, missing assistant content, non-string
content, oversized responses, and non-success HTTP responses.

The Streamlit UI displays a stable, sanitized failure message. Raw exception
text, response bodies, environment data, and credentials are not rendered to
the browser. Diagnostic details may be written to standard error for the
operator's container logs, subject to secret-safe formatting.

Lifecycle scripts fail closed when the image state is missing, the sandbox
does not become ready, Streamlit health fails, the forward cannot start, or the
effective policy is unavailable. Failed setup must not report the lab as ready.

## Verification and Evidence

Automated unit tests cover request construction, field omission, input and
history limits, response parsing, response-size enforcement, and sanitized UI
errors.

EARS requirements and Gherkin scenarios cover these externally observable
behaviors:

- the Streamlit application uses managed inference without credentials or a
  model selection;
- the application image runs as numeric non-root UID and GID 1500;
- the browser endpoint becomes reachable through the loopback forward;
- the protected process cannot write outside the declared runtime paths;
- the protected process cannot reach an undeclared host;
- the protected process has an empty capability bounding set and
  `NoNewPrivs=1`;
- the sandbox environment does not contain the OpenAI provider credential;
- configuration and runtime failures cannot produce a successful verification.

The Lab 5 verifier writes sanitized policy, process, health, and denial evidence
under `evidence/cpu/lab5/`. Generated evidence remains subject to the existing
repository safety rules and secret scan.

Local acceptance runs the full unit suite, all Gherkin scenarios, the EARS
audit, shell syntax and ShellCheck, YAML parsing, the repository secret scan,
and `git diff --check`. Remote acceptance additionally exercises the real CPU
host, OpenShell proxy, GPT-5.5 response, loopback forward, and four security
layers when the host is available.

## Documentation Migration

The useful content from `~/git/blog/openshell-why-it-matters.md` becomes a
workshop-owned document under `docs/`. The migration preserves its strongest
idea—an honest non-root baseline followed by four concrete protection
layers—but removes or corrects:

- OpenRouter configuration and provider-host examples;
- the hard-coded private address `192.168.1.101`;
- instructions that pass model credentials with `--env`;
- the plain-container deployment;
- claims that the application receives endpoint-bound credentials in its
  environment;
- stale statements that the blog repository is the source of truth.

The root README gains a concise “why OpenShell matters” section, a five-lab
progression, Lab 5 prerequisites and commands, the SSH tunnel command, expected
security results, and a link to the migrated narrative. The Lab 5 README is the
operator runbook and explicitly distinguishes local verification from remote
acceptance evidence.

## Non-Goals

Lab 5 does not provide arbitrary browser-driven shell tools, public internet
exposure, user authentication, multi-user persistent chat storage, OpenRouter
support, a vulnerable comparison deployment, Kubernetes manifests, or changes
to the source blog repository.

## Acceptance Criteria

Lab 5 is complete when:

1. The Streamlit image builds reproducibly and declares UID/GID 1500.
2. The app runs inside `openshell-lab5` on the existing CPU host.
3. A browser prompt receives a GPT-5.5 response through `inference.local`.
4. The app request contains neither model selection nor provider credentials.
5. Streamlit is reachable only through the documented loopback forward and SSH
   tunnel.
6. Filesystem, network, process, and provider-boundary verification passes.
7. The migrated narrative and root README contain no OpenRouter dependency,
   hard-coded blog host, or plaintext credential instructions.
8. EARS/Gherkin, unit, shell, YAML, and secret-scan verification passes.
