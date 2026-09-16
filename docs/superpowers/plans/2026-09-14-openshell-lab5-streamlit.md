# OpenShell Lab 5 Streamlit Implementation Plan

> **Numbering note:** This is a historical implementation record. The current
> workshop numbering is defined by
> `docs/superpowers/specs/2026-09-16-renumber-streamlit-lab4-gpu-lab5-design.md`:
> Streamlit is Lab 4 and GPU Qwen is Lab 5.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a containerized Streamlit Lab 5 on the existing CPU host that reaches GPT-5.5 only through OpenShell managed inference and demonstrates filesystem, process, network, and provider controls.

**Architecture:** A non-root Streamlit image runs inside the `openshell-lab5` sandbox and sends credential-free Chat Completions requests to `https://inference.local/v1/chat/completions`. OpenShell owns provider selection and credentials, while a loopback-only service forward and SSH tunnel expose the UI without opening a public Streamlit port.

**Tech Stack:** Python 3.11+, Streamlit 1.41.1, httpx 0.28.x, Bash, rootless Podman, OpenShell v0.0.116 or the dynamically resolved later stable release, EARS/Gherkin with Behave, unittest, RHEL 10, systemd user services.

**Spec:** `docs/superpowers/specs/2026-09-14-openshell-lab5-streamlit-design.md`

## Global Constraints

- Run Lab 5 on the guarded CPU instance used by Labs 1 through 3.
- Use only `https://inference.local/v1/chat/completions` for model traffic.
- Omit provider credentials, Authorization headers, provider hostnames, and model selection from application requests.
- Reuse the `openai-gpt55` provider configured by `labs/lab1/configure-openai.sh`.
- Use sandbox name `openshell-lab5`, internal Streamlit port `8501`, host loopback port `18501`, and systemd unit `openshell-lab5-forward.service`.
- Bind the host forward to `127.0.0.1`; never expose Streamlit on `0.0.0.0` or a public interface.
- Run the application image and OpenShell workload as numeric UID/GID `1500:1500`.
- Keep application code read-only and direct all application runtime state beneath `/tmp`.
- Permit no ordinary network egress in the Lab 5 policy.
- Limit prompts to 4,000 characters, retained history to 20 messages, HTTP timeout to 180 seconds, and model response bodies to 1 MiB.
- Preserve `~/git/blog` unchanged, including `openshell-why-it-matters.docx`.
- Use `apply_patch` for repository edits and keep generated connection, image, and evidence state out of Git.

## File Structure

- Create `src/openshell_lab/streamlit_inference.py`: framework-independent request validation, managed-inference HTTP client, response validation, and sanitized public errors.
- Create `tests/test_streamlit_inference.py`: behavioral tests for request boundaries and HTTP results.
- Create `features/0004-streamlit.feature`: EARS requirements and Gherkin acceptance scenarios for Lab 5.
- Create one new file per new Given/Then step under `features/steps/`; extend `features/steps/support/lab_checks.py` as the behavior adapter.
- Create `labs/lab5/app.py`: Streamlit-only presentation and session-state orchestration.
- Create `labs/lab5/probe.py`: non-UI managed-inference acceptance probe that uses the same client.
- Create `labs/lab5/requirements.txt`: pinned Streamlit and httpx runtime dependencies.
- Create `labs/lab5/Containerfile`: immutable-base, non-root Streamlit image definition.
- Create `policies/lab5-streamlit.yaml`: hard-required filesystem, process, and default-deny network policy.
- Create `tests/test_lab5.py`: image, policy, UI, lifecycle, and verifier artifact tests.
- Create `labs/lab5/build.sh`, `run.sh`, `verify.sh`, and `README.md`: image and sandbox lifecycle plus operator guidance.
- Extend `test_support/shell_lab_harness.py`: deterministic Lab 5 launcher fakes.
- Modify `infra/remote/run-cpu-labs.sh`, `infra/remote/install-runner.sh`, `scripts/collect-evidence.sh`, and their tests to include Lab 5.
- Create `docs/openshell-why-it-matters.md`: migrated and corrected workshop narrative.
- Modify `README.md`, `docs/evidence-index.md`, and `pyproject.toml` for Lab 5 documentation and dependencies.

---

### Task 1: Managed Inference Contract and Executable Requirements

**Files:**
- Create: `src/openshell_lab/streamlit_inference.py`
- Create: `tests/test_streamlit_inference.py`
- Create: `features/0004-streamlit.feature`
- Create: `features/steps/given/the_streamlit_prompt_is.py`
- Create: `features/steps/then/the_streamlit_request_should_use_managed_inference.py`
- Create: `features/steps/then/the_streamlit_input_should_be_rejected.py`
- Modify: `features/steps/support/lab_checks.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `build_chat_request(messages: list[dict[str, str]]) -> dict`
- Produces: `async call_managed_inference(messages: list[dict[str, str]], transport: httpx.AsyncBaseTransport | None = None) -> str`
- Produces: `public_error_message(error: Exception) -> str`
- Produces constants: `MODEL_URL`, `MAX_PROMPT_CHARS`, `MAX_HISTORY_MESSAGES`, `MAX_RESPONSE_BYTES`, `REQUEST_TIMEOUT`
- Consumes: OpenShell's existing managed `inference.local` route.

- [ ] **Step 1: Add EARS requirements and Gherkin scenarios before implementation**

Create `features/0004-streamlit.feature` with one `shall` per Rule and these scenarios:

```gherkin
@streamlit
@security
Feature: Streamlit managed inference
  Lab 5 serves a bounded chat UI through OpenShell without application credentials.

  @ubiquitous
  Rule: The Lab 5 Streamlit application shall send model requests through inference.local without provider credentials or model selection.

    Scenario: Streamlit request uses the managed inference route
      Given the "Lab 5 managed inference" configuration is available
      When the "Streamlit model request" is evaluated
      Then the Streamlit request should use managed inference

  @unwanted-behavior
  Rule: If a Lab 5 prompt is empty or exceeds 4000 characters, then the Streamlit inference client shall reject it before model access.

    Scenario Outline: Invalid Streamlit input is rejected
      Given the Streamlit prompt is "<prompt_state>"
      When the "Streamlit input validation" is evaluated
      Then the Streamlit input should be rejected

      Examples:
        | prompt_state        |
        | empty               |
        | over 4000 characters |
```

Add `load_configuration("Lab 5 managed inference")`, prompt fixture setup,
request evaluation, and assertions to `LabChecks`. The new Given step maps the
two named prompt states to `""` and `"x" * 4001`. Each new step file must
contain exactly one thin Behave step and delegate to `LabChecks`.

- [ ] **Step 2: Write failing unit tests for the managed inference client**

Create tests that assert the exact endpoint and forbidden-field boundary:

```python
class StreamlitInferenceTests(unittest.TestCase):
    def test_request_uses_managed_route_without_model_or_credentials(self):
        request = build_chat_request([{"role": "user", "content": "hello"}])
        self.assertEqual(
            "https://inference.local/v1/chat/completions", MODEL_URL
        )
        self.assertEqual(
            {"messages", "temperature", "max_completion_tokens"}, set(request)
        )
        self.assertFalse(
            {"model", "api_key", "authorization", "headers"}.intersection(request)
        )

    def test_empty_and_oversized_prompts_are_rejected(self):
        for prompt in ("", "x" * 4001):
            with self.subTest(length=len(prompt)):
                with self.assertRaises(ValueError):
                    build_chat_request([{"role": "user", "content": prompt}])

    def test_history_is_limited_to_twenty_messages(self):
        messages = [
            {"role": "user", "content": str(index)} for index in range(21)
        ]
        with self.assertRaises(ValueError):
            build_chat_request(messages)
```

Use `httpx.MockTransport` to cover a successful assistant response, HTTP 403,
malformed JSON, missing content, non-string content, and a body larger than
`MAX_RESPONSE_BYTES`. Assert `public_error_message` always returns
`"Managed inference is temporarily unavailable. Please try again."` without
including raw exception text.

- [ ] **Step 3: Run the new requirements and unit tests to verify RED**

Run:

```bash
uv run python -m unittest tests.test_streamlit_inference
PYTHONPATH=src uv run behave features/0004-streamlit.feature
```

Expected: unit import failure for `openshell_lab.streamlit_inference` and
Gherkin failure because the Lab 5 behavior adapter is not implemented.

- [ ] **Step 4: Implement the bounded managed-inference client**

Add `httpx>=0.28.1,<0.29` to project dependencies and run `uv lock`. Implement
message validation with allowed roles `system`, `user`, and `assistant`; require
non-empty string content; enforce the exact prompt/history limits; and return:

```python
{
    "messages": validated_messages,
    "temperature": 1.0,
    "max_completion_tokens": 1000,
}
```

Implement `call_managed_inference` using `httpx.AsyncClient` and a streamed
`POST` with `json=build_chat_request(messages)`, no application-supplied
headers, `trust_env=True`, and `timeout=REQUEST_TIMEOUT`. Accumulate bytes until
EOF, raise `ValueError("managed inference response exceeds 1 MiB")` before the
limit is crossed, parse JSON, and require
`payload["choices"][0]["message"]["content"]` to be a non-empty string.

- [ ] **Step 5: Implement the thin Gherkin adapter and steps**

Make `LabChecks.evaluate_subject("Streamlit model request")` call the real
`build_chat_request` with one user message and store both `MODEL_URL` and the
request. Make input validation call the same function and store whether it
raised `ValueError`. Assertions must reject any recursively nested credential
key or value using the existing managed-request scanner and must additionally
reject a `model` field. Implement the new Given and two Then files as thin
delegations to these support methods.

- [ ] **Step 6: Run Task 1 verification to confirm GREEN**

Run:

```bash
uv run python -m unittest tests.test_streamlit_inference tests.test_lab_checks
PYTHONPATH=src uv run behave features/0004-streamlit.feature
PYTHONPATH=src uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py features/
```

Expected: all commands exit 0, the feature has three passing scenario examples,
and the audit reports no missing, unused, duplicate, or malformed steps.

- [ ] **Step 7: Commit the managed inference contract**

```bash
git add pyproject.toml uv.lock src/openshell_lab/streamlit_inference.py \
  tests/test_streamlit_inference.py features/0004-streamlit.feature \
  features/steps/support/lab_checks.py \
  features/steps/given/the_streamlit_prompt_is.py \
  features/steps/then/the_streamlit_request_should_use_managed_inference.py \
  features/steps/then/the_streamlit_input_should_be_rejected.py
git commit -m "Add Lab 5 managed inference contract"
```

### Task 2: Streamlit Image and Security Policy

**Files:**
- Create: `labs/lab5/app.py`
- Create: `labs/lab5/probe.py`
- Create: `labs/lab5/requirements.txt`
- Create: `labs/lab5/Containerfile`
- Create: `policies/lab5-streamlit.yaml`
- Create: `tests/test_lab5.py`
- Modify: `features/0004-streamlit.feature`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Consumes: `build_chat_request`, `call_managed_inference`, and `public_error_message` from Task 1.
- Produces image: `localhost/openshell-lab-streamlit:<12-character-git-sha>`.
- Produces policy: hard-required Landlock, UID/GID 1500, no ordinary network policies.

- [ ] **Step 1: Extend EARS/Gherkin for image and policy boundaries**

Append these Rules and scenarios to `features/0004-streamlit.feature` before
creating production artifacts:

```gherkin
  @ubiquitous
  Rule: The Lab 5 application image shall run Streamlit with the numeric non-root identity 1500:1500.

    Scenario: Streamlit image declares the approved identity
      Given the "Streamlit image metadata" configuration is available
      When the "image identity" is evaluated
      Then the image identity should be non-root

  @state-driven
  Rule: While Lab 5 is active, the OpenShell filesystem policy shall expose application code as read-only and confine runtime writes to /tmp and /dev/null.

    Scenario: Streamlit runtime state is writable
      Given the "Lab 5" policy is loaded
      When the report agent writes beneath "/tmp"
      Then the filesystem action should be "allowed"

    Scenario: Streamlit application code is not writable
      Given the "Lab 5" policy is loaded
      When the report agent writes beneath "/opt/openshell-lab/app.py"
      Then the filesystem action should be "denied"

  @state-driven
  Rule: While Lab 5 is active, the OpenShell network policy shall deny all ordinary egress.

    Scenario: Lab 5 ordinary egress is absent
      Given the "Lab 5" policy is loaded
      When the "Lab 5 network posture" is evaluated
      Then the Lab 5 ordinary network policy should be empty
```

Reuse existing Given/When/Then steps where their language matches. Add only
`features/steps/then/the_lab_5_ordinary_network_policy_should_be_empty.py` for
the new assertion.

- [ ] **Step 2: Write failing artifact and policy tests**

Create `tests/test_lab5.py` with YAML parsing and source assertions:

```python
def test_policy_is_hard_required_and_default_deny(self):
    self.assertEqual("hard_requirement", self.policy["landlock"]["compatibility"])
    self.assertEqual({}, self.policy["network_policies"])
    self.assertEqual("1500", self.policy["process"]["run_as_user"])
    self.assertEqual("1500", self.policy["process"]["run_as_group"])
    self.assertEqual(
        ["/tmp", "/dev/null"], self.policy["filesystem_policy"]["read_write"]
    )
    self.assertIn(
        "/opt/openshell-lab", self.policy["filesystem_policy"]["read_only"]
    )

def test_container_is_nonroot_keyless_and_uses_managed_inference(self):
    self.assertIn("USER 1500:1500", self.containerfile)
    self.assertIn("streamlit run app.py", self.containerfile)
    self.assertIn("PYTHONDONTWRITEBYTECODE=1", self.containerfile)
    self.assertNotIn("OPENAI_API_KEY", self.containerfile + self.app)
    self.assertNotIn("Authorization", self.containerfile + self.app)
    self.assertNotIn("openrouter", (self.containerfile + self.app).lower())
```

Also assert the Containerfile starts from the exact digest in
`container/base-image.lock`, copies only the Lab 5 app/probe and inference
package, uses `/tmp/streamlit-home`, exposes 8501, and contains no `.env`, key,
credential, or private-address copy source.

- [ ] **Step 3: Run Task 2 tests to verify RED**

Run:

```bash
uv run python -m unittest tests.test_lab5
PYTHONPATH=src uv run behave features/0004-streamlit.feature
```

Expected: failures report missing `labs/lab5/Containerfile`, app, probe,
requirements, and `policies/lab5-streamlit.yaml`.

- [ ] **Step 4: Implement the Streamlit app and probe**

The app must configure page title `OpenShell Lab 5`, initialize
`st.session_state.messages`, display the four active control layers, accept one
prompt through `st.chat_input`, construct a system message plus the last 20
conversation messages, and call `asyncio.run(call_managed_inference(...))`.
Catch `Exception`, log only its exception class to standard error, and render
`public_error_message(error)`.

The probe accepts `--prompt`, defaults to
`Reply with exactly: OpenShell managed inference is working`, calls the same
client, and prints compact JSON with keys `status` and `response`. It must print
no environment variables, headers, endpoint credentials, or raw response body
on failure.

- [ ] **Step 5: Implement the image and policy**

Pin `streamlit==1.41.1` and `httpx==0.28.1` in requirements. Use this exact base
reference:

```Dockerfile
FROM quay.io/aipcc/agentic-ci/openshell@sha256:06a978ed76d32f2341f9a36271a5ce21cf64a9a562b0eb04d0d9eb1aeb23729f
```

Install `python3`, `python3-pip`, and `shadow-utils`; create UID/GID 1500; copy
dependencies, app, probe, `src/openshell_lab/__init__.py`, and
`src/openshell_lab/streamlit_inference.py` with ownership 1500:1500; set
`HOME=/tmp/streamlit-home`, `PYTHONPATH=/opt/openshell-lab`,
`PYTHONDONTWRITEBYTECODE=1`, and
`STREAMLIT_BROWSER_GATHER_USAGE_STATS=false`; declare `USER 1500:1500`; expose
8501; and run Streamlit headless on `0.0.0.0:8501`.

The policy sets `include_workdir: false`, read-only paths `/usr`, `/lib64`,
`/etc`, `/proc`, `/dev/urandom`, and `/opt/openshell-lab`; writable paths
`/tmp` and `/dev/null`; Landlock `hard_requirement`; process UID/GID 1500; and
`network_policies: {}`.

- [ ] **Step 6: Implement behavior adapters and run Task 2 GREEN verification**

Map `"Lab 5"` to `policies/lab5-streamlit.yaml`, map
`"Streamlit image metadata"` to the new Containerfile, evaluate the empty
network-policy invariant, and assert it from the one new Then step.

Run:

```bash
uv run python -m unittest tests.test_lab5 tests.test_streamlit_inference
PYTHONPATH=src uv run behave features/0004-streamlit.feature
PYTHONPATH=src uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py features/
bash -n labs/lab5/*.sh 2>/dev/null || test ! -e labs/lab5/build.sh
```

Expected: unit, Gherkin, and audit commands exit 0. The conditional shell check
exits 0 because lifecycle scripts are introduced in Task 3.

- [ ] **Step 7: Commit the Streamlit application boundary**

```bash
git add labs/lab5/app.py labs/lab5/probe.py labs/lab5/requirements.txt \
  labs/lab5/Containerfile policies/lab5-streamlit.yaml tests/test_lab5.py \
  features/0004-streamlit.feature features/steps/support/lab_checks.py \
  features/steps/then/the_lab_5_ordinary_network_policy_should_be_empty.py
git commit -m "Add protected Lab 5 Streamlit image"
```

### Task 3: Lab 5 Build, Sandbox, Forward, and Verification Lifecycle

**Files:**
- Create: `labs/lab5/build.sh`
- Create: `labs/lab5/run.sh`
- Create: `labs/lab5/verify.sh`
- Modify: `tests/test_lab5.py`
- Modify: `test_support/shell_lab_harness.py`
- Modify: `tests/test_sandbox_launchers.py`
- Modify: `features/0004-streamlit.feature`
- Modify: `features/steps/support/lab_checks.py`
- Create: `features/steps/then/the_lab_5_forward_should_be_loopback_only.py`

**Interfaces:**
- Consumes image from Task 2 and managed inference client from Task 1.
- Produces state file `state/lab5-image.env` with `IMAGE=localhost/openshell-lab-streamlit:<sha>`.
- Produces loopback service `127.0.0.1:18501` backed by sandbox port 8501.
- Produces sanitized evidence under `evidence/cpu/lab5/`.

- [ ] **Step 1: Add the lifecycle EARS requirement**

Append before implementation:

```gherkin
  @security
  @state-driven
  Rule: While Lab 5 is available to a browser, the Streamlit forward shall maintain a durable loopback-only mapping from host port 18501 to sandbox port 8501.

    Scenario: Streamlit uses a durable loopback-only forward
      Given the "Lab 5 launcher" configuration is available
      When the "Lab 5 forward configuration" is evaluated
      Then the Lab 5 forward should be loopback only
```

- [ ] **Step 2: Write failing lifecycle tests and deterministic launcher fake**

Extend `tests/test_lab5.py` to require:

```python
def test_build_records_commit_addressed_nonroot_image(self):
    self.assertIn("localhost/openshell-lab-streamlit:$short_sha", self.build)
    self.assertIn("state/lab5-image.env", self.build)
    self.assertIn("1500:1500", self.build)

def test_run_uses_durable_loopback_forward(self):
    self.assertIn("openshell-lab5", self.run)
    self.assertIn("-- /usr/bin/sleep infinity", self.run)
    self.assertIn("--target-port 8501", self.run)
    self.assertIn("--local 127.0.0.1:18501", self.run)
    self.assertIn("systemd-run --user", self.run)
    self.assertNotIn("0.0.0.0:18501", self.run)

def test_verifier_covers_four_layers_and_model_probe(self):
    for marker in (
        "probe.py", "example.com", "/opt/openshell-lab/lab5-write-denied",
        "CapBnd", "NoNewPrivs", "OPENAI_API_KEY", "policy.json",
    ):
        self.assertIn(marker, self.verify)
```

Add `run_lab5_launcher(repository: Path) -> LauncherResult` to the harness. It
must copy the real Lab 5 run script into a temporary repository, create valid
image state, and install fakes for `podman`, `openshell`, `systemctl`,
`systemd-run`, `curl`, and `sleep`. Record ordered events for sandbox deletion,
creation, Streamlit start, internal health, forward creation, and host health.
The launcher test must assert completion within two seconds and this order:

```python
(
    "sandbox-create",
    "streamlit-start",
    "internal-health",
    "forward-start",
    "host-health",
)
```

- [ ] **Step 3: Run lifecycle tests to verify RED**

Run:

```bash
uv run python -m unittest tests.test_lab5 tests.test_sandbox_launchers
PYTHONPATH=src uv run behave features/0004-streamlit.feature
```

Expected: failures report missing build, run, verify, and forward configuration.

- [ ] **Step 4: Implement `build.sh`**

Follow Lab 3's commit-tag validation, build from repository root with the Lab 5
Containerfile, inspect `.Config.User`, require exact `1500:1500`, and atomically
write owner-only `state/lab5-image.env`. Reject a missing or malformed Git SHA
and never emit credentials.

- [ ] **Step 5: Implement `run.sh` fail-closed lifecycle**

Validate image state against
`^localhost/openshell-lab-streamlit:[0-9a-f]{7,12}$`. Stop and reset
`openshell-lab5-forward.service`, delete an existing sandbox, and wait at most
60 seconds for deletion. Create the sandbox with `lab5-streamlit.yaml`, capture
creation diagnostics in `evidence/cpu/lab5/sandbox-create.log`, and keep
`/usr/bin/sleep infinity` as the canonical process.

Start Streamlit with a bounded `openshell sandbox exec` command using
`nohup streamlit run app.py --server.port=8501 --server.address=0.0.0.0
--server.headless=true`, stdin from `/dev/null`, and logs at
`/tmp/streamlit.log`. Probe `http://127.0.0.1:8501/_stcore/health` from inside
the sandbox for at most 60 seconds.

Start the forward with:

```bash
systemd-run --user --unit=openshell-lab5-forward --collect -- \
  openshell forward service openshell-lab5 \
    --target-port 8501 --local 127.0.0.1:18501
```

Probe host loopback health for at most 30 seconds. Any command or timeout must
exit nonzero and must not print a ready message.

- [ ] **Step 6: Implement `verify.sh` four-layer acceptance**

Require image UID/GID 1500, active forward unit, loopback health, full effective
policy, and a successful `probe.py` result. Store probe JSON, policy JSON,
process status, denial audit log, and health result beneath
`evidence/cpu/lab5/`.

Verify code writes fail at `/opt/openshell-lab/lab5-write-denied`; a bounded
Python request to `https://example.com` fails and produces a matching OpenShell
network-denial audit event; `CapBnd` is all zeroes; `NoNewPrivs` is 1;
`unshare -Urn true` fails; and `OPENAI_API_KEY`, `OPENAI_KEY`, and
`AUTHORIZATION` are absent from the workload environment. Never print the
environment or provider state.

- [ ] **Step 7: Implement behavior adapter and run Task 3 GREEN verification**

Load the Lab 5 run script for `"Lab 5 launcher"`. Evaluate exact markers,
ordering, loopback address, target port, and systemd durability. Add one thin
Then step delegating to `LabChecks.assert_lab5_forward_loopback_only()`.

Run:

```bash
uv run python -m unittest tests.test_lab5 tests.test_sandbox_launchers
PYTHONPATH=src uv run behave features/0004-streamlit.feature
PYTHONPATH=src uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py features/
bash -n labs/lab5/*.sh
shellcheck labs/lab5/*.sh
```

Expected: every command exits 0 and the fake launcher proves the invoking
session is released while the forward remains delegated to systemd.

- [ ] **Step 8: Commit the Lab 5 lifecycle**

```bash
git add labs/lab5/build.sh labs/lab5/run.sh labs/lab5/verify.sh \
  tests/test_lab5.py tests/test_sandbox_launchers.py \
  test_support/shell_lab_harness.py features/0004-streamlit.feature \
  features/steps/support/lab_checks.py \
  features/steps/then/the_lab_5_forward_should_be_loopback_only.py
git commit -m "Add Lab 5 Streamlit lifecycle"
```

### Task 4: CPU Orchestration and Evidence Collection

**Files:**
- Modify: `infra/remote/run-cpu-labs.sh`
- Modify: `infra/remote/install-runner.sh`
- Modify: `scripts/collect-evidence.sh`
- Modify: `test_support/shell_lab_harness.py`
- Modify: `tests/test_deployment_orchestration.py`
- Modify: `tests/test_remote_installers.py`
- Modify: `features/0003-aws-deployment.feature`
- Modify: `features/steps/support/lab_checks.py`
- Create: `features/steps/then/lab_5_should_follow_lab_3_without_reusing_its_forward.py`

**Interfaces:**
- Consumes: executable Lab 5 build/run/verify scripts from Task 3.
- Produces: end-to-end CPU sequence ending with Lab 5.
- Produces: locally collected `evidence/cpu/lab5/` without provider inspection.

- [ ] **Step 1: Add orchestration requirement before production edits**

Append to `features/0003-aws-deployment.feature`:

```gherkin
  @reliability
  @event-driven
  Rule: When Lab 3 verification completes, the CPU deployment shall execute the Lab 5 lifecycle on its distinct port 18501.

    Scenario: Lab 5 follows the report labs on a distinct forward
      Given the "CPU lab sequence" configuration is available
      When the "CPU Lab 5 sequence" is evaluated
      Then Lab 5 should follow Lab 3 without reusing its forward
```

- [ ] **Step 2: Write failing orchestration tests**

Extend the CPU sequence harness to create fake `lab5/build.sh`, `run.sh`, and
`verify.sh` event writers. Assert exact tail order:

```python
self.assertEqual(
    ["lab5-build", "lab5-run", "lab5-verify"], events[-3:]
)
```

Assert the installed runner accepts `lab5`, its usage includes `lab5`, and it
validates `labs/lab5/run.sh`. Assert evidence collection archives remote
`evidence/cpu/lab5` through the existing redaction boundary and does not invoke
`openshell provider get` or print environment variables.

- [ ] **Step 3: Run orchestration tests to verify RED**

Run:

```bash
uv run python -m unittest tests.test_deployment_orchestration tests.test_remote_installers
PYTHONPATH=src uv run behave features/0003-aws-deployment.feature
```

Expected: failures show Lab 5 missing from sequence, runner, evidence, and BDD
adapter.

- [ ] **Step 4: Implement CPU sequence and runner changes**

After Lab 3 verification, invoke Lab 5 build, run, and verify. Do not stop or
reuse port 18080; Lab 5 owns 18501. Extend the home runner's validation loop,
case pattern, and usage string to include `lab5`, while retaining the existing
default selection behavior.

- [ ] **Step 5: Implement bounded evidence collection**

Archive only `evidence/cpu/lab5` from the remote repository and extract it under
local `evidence/cpu/`. Keep the existing redaction function in the pipe. Add
Lab 5 health and policy artifacts to `docs/evidence-index.md` only after remote
evidence exists; otherwise label them as expected remote acceptance artifacts.

- [ ] **Step 6: Implement BDD adapter and run Task 4 GREEN verification**

Evaluate `"CPU Lab 5 sequence"` through the real sequence harness, assert Lab 3
verify precedes Lab 5 build, and assert Lab 5 markers do not contain port 18080.

Run:

```bash
uv run python -m unittest tests.test_deployment_orchestration tests.test_remote_installers
PYTHONPATH=src uv run behave features/0003-aws-deployment.feature
PYTHONPATH=src uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py features/
bash -n infra/remote/*.sh scripts/*.sh
shellcheck infra/remote/*.sh scripts/*.sh
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit CPU orchestration**

```bash
git add infra/remote/run-cpu-labs.sh infra/remote/install-runner.sh \
  scripts/collect-evidence.sh test_support/shell_lab_harness.py \
  tests/test_deployment_orchestration.py tests/test_remote_installers.py \
  features/0003-aws-deployment.feature features/steps/support/lab_checks.py \
  features/steps/then/lab_5_should_follow_lab_3_without_reusing_its_forward.py
git commit -m "Integrate Lab 5 into CPU deployment"
```

### Task 5: Narrative Migration and Operator Guidance

**Files:**
- Create: `docs/openshell-why-it-matters.md`
- Create: `labs/lab5/README.md`
- Modify: `README.md`
- Modify: `docs/evidence-index.md`
- Modify: `tests/test_lab5.py`

**Interfaces:**
- Consumes: final commands, ports, sandbox names, and controls from Tasks 1–4.
- Produces: workshop narrative and exact Lab 5 runbook.

- [ ] **Step 1: Write failing documentation-boundary tests**

Add tests that load the root README, Lab 5 README, and migrated narrative and
assert all three identify `inference.local`, `openshell-lab5`, and the four
control layers. Require exact SSH guidance:

```text
ssh -N -L 8501:127.0.0.1:18501
```

Assert the root README and Lab 5 README contain no case-insensitive
`openrouter`, `192.168.1.101`, `LLM_API_KEY`, `--env OPENAI_API_KEY`, or public
`0.0.0.0:18501`. Assert the narrative says the application request omits model
and credential fields and that provider credentials remain outside the image,
environment, filesystem, and request body.

- [ ] **Step 2: Run documentation tests to verify RED**

Run:

```bash
uv run python -m unittest tests.test_lab5
```

Expected: failures report missing narrative and Lab 5 runbook and missing root
README guidance.

- [ ] **Step 3: Migrate and correct the why-it-matters narrative**

Use `~/git/blog/openshell-why-it-matters.md` as source material without copying
its environment-key examples or private host. Preserve the honest non-root
baseline, the comparison with SELinux/firewalld/containers, the four-layer
explanation, and concrete verification commands. Reframe the demonstration as
five progressive workshop labs and make Lab 5 the provider-bound Streamlit
example. State explicitly that the source of truth is `openshell-lab`.

- [ ] **Step 4: Write the Lab 5 runbook and enhance the root README**

Document prerequisites, provider reuse, build/run/verify commands, readiness
URL, SSH tunnel, expected denials, evidence paths, inspection commands, and
explicit cleanup:

```bash
systemctl --user stop openshell-lab5-forward.service
openshell sandbox delete openshell-lab5
```

Update the workshop overview from four labs to five, explain why managed proxy
access matters, link the narrative and Lab 5 runbook, and preserve existing Lab
1–4 commands.

- [ ] **Step 5: Run documentation GREEN verification and secret scan**

Run:

```bash
uv run python -m unittest tests.test_lab5
./scripts/scan-secrets.sh .
git diff --check
```

Expected: tests exit 0, scanner prints `secret-scan: clean`, and diff check is
silent.

- [ ] **Step 6: Commit the migrated narrative and guidance**

```bash
git add docs/openshell-why-it-matters.md labs/lab5/README.md README.md \
  docs/evidence-index.md tests/test_lab5.py
git commit -m "Document the Lab 5 Streamlit workshop"
```

### Task 6: Full Verification, Remote Acceptance, and Final Review

**Files:**
- Modify when remote evidence succeeds: `docs/evidence-index.md`
- Generated and normally ignored: `state/lab5-image.env`, `evidence/cpu/lab5/*`

**Interfaces:**
- Consumes: completed Lab 5 implementation and existing CPU connection state.
- Produces: verified local tree, optional refreshed remote evidence, and review findings.

- [ ] **Step 1: Run the complete local verification suite**

```bash
./scripts/verify-all.sh
```

Expected: all unit tests and Gherkin scenarios pass; the EARS audit, Bash
syntax, ShellCheck when installed, YAML parsing, diagram validation, secret
scan, and diff check exit 0.

- [ ] **Step 2: Inspect CPU host availability without changing it**

```bash
source state/cpu-connection.env
aws --no-cli-pager --region "$AWS_REGION" ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].[InstanceId,State.Name,InstanceType]' \
  --output text
```

Expected: the exact guarded instance identity with state `running` or
`stopped`. If stopped, use `infra/aws/start-cpu.sh`; if unavailable, record
remote acceptance as blocked without weakening local verification.

- [ ] **Step 3: Deploy and run Lab 5 on the guarded CPU host**

Use the existing strict-known-hosts and rsync exclusions from
`scripts/deploy-cpu.sh`. Do not request or resend the OpenAI credential when
`openshell inference get` already reports the configured `openai-gpt55` route.
On the host run:

```bash
cd "$HOME/git/openshell-lab"
./labs/lab5/build.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
```

Expected: image identity 1500:1500, healthy loopback endpoint, successful
managed GPT-5.5 probe, four-layer verification, and no provider credential in
application state.

- [ ] **Step 4: Verify the documented SSH tunnel from the local machine**

Start the documented tunnel with strict known-host checking, then request:

```bash
curl --silent --show-error --fail \
  http://127.0.0.1:8501/_stcore/health
```

Expected: HTTP 200 and body `ok`. Stop only the local SSH tunnel; leave the Lab
5 sandbox running for inspection unless the user requests cleanup.

- [ ] **Step 5: Collect sanitized Lab 5 evidence and rescan**

Run `scripts/collect-evidence.sh`, inspect every new Lab 5 artifact for secrets,
and run:

```bash
./scripts/scan-secrets.sh .
git diff --check
```

Expected: no secret match and no whitespace error. Commit only sanitized,
intentional evidence; leave raw and mutable connection state ignored.

- [ ] **Step 6: Request independent code review and resolve findings**

Ask a read-only reviewer to compare the implementation against the design spec
and this plan, with emphasis on credential boundaries, forward binding,
fail-closed verification, test realism, and documentation accuracy. Fix every
Critical and Important issue, then rerun affected targeted tests.

- [ ] **Step 7: Run fresh final verification and commit remaining changes**

```bash
./scripts/verify-all.sh
git status --short
```

Expected: verification exits 0 and status contains only intentional final
evidence or documentation changes. Commit those exact paths with:

```bash
git commit -m "Verify Lab 5 Streamlit acceptance"
```

If there are no remaining tracked changes, do not create an empty commit.
