# Renumber Streamlit Lab 4 and GPU Lab 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Labs 1 through 4 a progressive CPU-host sequence by renumbering Streamlit as Lab 4 and moving the capacity-sensitive Qwen/vLLM GPU exercise to Lab 5.

**Architecture:** Perform a clean semantic swap with no compatibility aliases. Rename every active runtime identity, path, test, and public instruction; regenerate CPU Lab 4 evidence; attempt the exact guarded GPU host for Lab 5 evidence; and stop both instances after acceptance.

**Tech Stack:** Bash, Python 3.12+, unittest, Behave/Gherkin, EARS audit, OpenShell 0.0.116+, Podman, Streamlit, vLLM, AWS EC2, systemd user services.

**Spec:** `docs/superpowers/specs/2026-09-16-renumber-streamlit-lab4-gpu-lab5-design.md`

## Global Constraints

- Streamlit is Lab 4 and runs on the existing guarded CPU `t3.micro` after Labs 1 through 3.
- GPU Qwen/vLLM is Lab 5 and runs only on the exact guarded `g6.12xlarge` when EC2 capacity is available.
- Streamlit model requests continue to use only `https://inference.local/v1/chat/completions` without provider credentials or model selection.
- Streamlit uses sandbox `openshell-lab4`, policy `policies/lab4-streamlit.yaml`, state `state/lab4-image.env`, service `openshell-lab4-forward.service`, and loopback port `18401`.
- GPU Qwen uses sandbox `openshell-lab5`, image tag `localhost/openshell-lab-agent:lab5`, and GPU-host report port `18080`.
- No compatibility aliases may leave two meanings for Lab 4 or Lab 5.
- Old-numbered CPU and GPU acceptance evidence is deleted, not archived.
- New evidence is committed only after its corresponding remote verification succeeds.
- Do not launch a replacement GPU instance or broaden the guarded GPU identity.
- Stop and verify both CPU and GPU instances after remote acceptance, including failure paths.
- Use `apply_patch` for content edits and mechanical `git mv` only for path swaps and renames.

---

### Task 1: Specify the new numbering and prove RED

**Files:**
- Modify: `features/0003-aws-deployment.feature`
- Modify: `features/0004-streamlit.feature`
- Modify: `tests/test_deployment_orchestration.py`
- Modify: `tests/test_sandbox_launchers.py`
- Modify: `tests/test_lab5.py`
- Modify: `tests/test_lab5_policy.py`
- Modify: `tests/test_lab5_verifier.py`
- Modify: `tests/test_streamlit_inference.py`

**Interfaces:**
- Consumes: current Lab 4 GPU and Lab 5 Streamlit paths.
- Produces: executable requirements that demand Lab 4 Streamlit and Lab 5 GPU identities before implementation changes exist.

- [ ] **Step 1: Update the EARS requirements without changing implementation**

In `features/0003-aws-deployment.feature`, replace the CPU Lab 5 rule with these two requirements and scenarios:

```gherkin
  @event-driven
  Rule: When Lab 3 verification completes, the CPU deployment shall execute the Lab 4 Streamlit lifecycle on its distinct port 18401.

    Scenario: Lab 4 follows the report labs on a distinct forward
      Given the "CPU lab sequence" configuration is available
      When the "CPU Lab 4 sequence" is evaluated
      Then Lab 4 should follow Lab 3 without invoking Lab 5

  @state-driven
  Rule: While vLLM is active, the generated home runner shall select Lab 5 as its default lab.

    Scenario: GPU host defaults to Lab 5
      Given the "home runner installer" configuration is available
      When the "GPU default lab" is evaluated
      Then the generated runner should default to Lab 5
```

In `features/0004-streamlit.feature`, replace every active `Lab 5` reference with `Lab 4`, change `18501` to `18401`, and use these scenario phrases where renaming requires new steps:

```gherkin
    Scenario: Lab 4 ordinary egress is absent
      Given the "Lab 4" policy is loaded
      When the "Lab 4 network posture" is evaluated
      Then the Lab 4 ordinary network policy should be empty

    Scenario: Streamlit uses a durable loopback-only forward
      Given the "Lab 4 launcher" configuration is available
      When the "Lab 4 forward configuration" is evaluated
      Then the Lab 4 forward should be loopback only
```

- [ ] **Step 2: Change unit expectations to the new contract**

Update the existing tests before moving files. Required assertions include:

```python
self.assertIn("./labs/lab4/build.sh", cpu_sequence)
self.assertNotIn("./labs/lab5/", cpu_sequence)
self.assertIn("lab=lab5", runner_installer)
self.assertIn("--local 127.0.0.1:18401", streamlit_run)
self.assertIn('SANDBOX="openshell-lab4"', streamlit_run)
self.assertIn('SANDBOX="openshell-lab5"', gpu_run)
self.assertIn("localhost/openshell-lab-agent:lab5", gpu_run)
```

Keep the current test filenames temporarily so the RED run isolates behavioral mismatch rather than missing imports.

- [ ] **Step 3: Run the new contract and confirm RED**

Run:

```bash
uv run python -m unittest \
  tests.test_deployment_orchestration \
  tests.test_sandbox_launchers \
  tests.test_lab5 \
  tests.test_lab5_policy \
  tests.test_lab5_verifier \
  tests.test_streamlit_inference
PYTHONPATH=src uv run behave features/0003-aws-deployment.feature features/0004-streamlit.feature
```

Expected: failures mention the old Lab 5 Streamlit paths, port `18501`, old CPU sequence, or undefined newly renamed steps. A green result is invalid and requires strengthening the assertions before continuing.

- [ ] **Step 4: Commit the failing executable specification**

```bash
git add features/0003-aws-deployment.feature features/0004-streamlit.feature tests
git commit -m "Specify the Lab 4 and Lab 5 ordering"
```

---

### Task 2: Swap the implementations and make the core contract GREEN

**Files:**
- Rename: `labs/lab4/` to temporary, `labs/lab5/` to `labs/lab4/`, temporary to `labs/lab5/`
- Rename: `policies/lab5-streamlit.yaml` to `policies/lab4-streamlit.yaml`
- Rename: `src/openshell_lab/lab5_policy.py` to `src/openshell_lab/lab4_policy.py`
- Rename: `tests/test_lab5.py` to `tests/test_lab4.py`
- Rename: `tests/test_lab5_policy.py` to `tests/test_lab4_policy.py`
- Rename: `tests/test_lab5_verifier.py` to `tests/test_lab4_verifier.py`
- Modify: `src/openshell_lab/streamlit_inference.py`
- Modify: `test_support/shell_lab_harness.py`
- Modify: `features/steps/support/lab_checks.py`
- Rename: Lab-number-specific files under `features/steps/then/`

**Interfaces:**
- Consumes: Task 1 requirements and existing Streamlit/GPU implementations.
- Produces: `run_lab4_launcher(...)`, `run_lab4_verifier(...)`, `validate_effective_policy(...)` in `openshell_lab.lab4_policy`, and live `labs/lab4` Streamlit plus `labs/lab5` GPU paths.

- [ ] **Step 1: Exchange the lab directories and rename supporting files**

Run these mechanical path operations exactly from the repository root:

```bash
git mv labs/lab4 labs/lab-gpu-swap
git mv labs/lab5 labs/lab4
git mv labs/lab-gpu-swap labs/lab5
git mv policies/lab5-streamlit.yaml policies/lab4-streamlit.yaml
git mv src/openshell_lab/lab5_policy.py src/openshell_lab/lab4_policy.py
git mv tests/test_lab5.py tests/test_lab4.py
git mv tests/test_lab5_policy.py tests/test_lab4_policy.py
git mv tests/test_lab5_verifier.py tests/test_lab4_verifier.py
```

- [ ] **Step 2: Rename Streamlit runtime identities**

Apply focused edits under `labs/lab4/`, `src/openshell_lab/`, and the renamed tests:

```text
Lab 5                         -> Lab 4
lab5                          -> lab4
openshell-lab5                -> openshell-lab4
lab5-image.env                -> lab4-image.env
lab5-streamlit.yaml           -> lab4-streamlit.yaml
openshell_lab.lab5_policy     -> openshell_lab.lab4_policy
openshell-lab5-forward        -> openshell-lab4-forward
127.0.0.1:18501               -> 127.0.0.1:18401
sport = :18501                -> sport = :18401
evidence/cpu/lab5             -> evidence/cpu/lab4
```

Update every `COPY labs/lab5/...` source in `labs/lab4/Containerfile` to
`COPY labs/lab4/...`. Rename harness functions and result messages:

```python
def run_lab4_launcher(repository: Path) -> LauncherResult: ...

def run_lab4_verifier(
    repository: Path,
    *,
    filesystem_mode: str = "denied",
    namespace_mode: str = "denied",
    unit_bind: str = "127.0.0.1:18401",
    listener_bind: str = "127.0.0.1:18401",
) -> subprocess.CompletedProcess: ...
```

- [ ] **Step 3: Rename GPU runtime identities without changing topology**

Under `labs/lab5/`, change only lab identity strings:

```text
Lab 4                                     -> Lab 5
openshell-lab4                            -> openshell-lab5
localhost/openshell-lab-agent:lab4        -> localhost/openshell-lab-agent:lab5
lab4-write-denied                         -> lab5-write-denied
lab4 verification passed                  -> lab5 verification passed
```

Do not alter `g6-l4`, `g6e-l40s`, the four-GPU profiles, Qwen model name,
tensor parallelism, context length, concurrency limits, or port `18080`.

- [ ] **Step 4: Implement the renamed Gherkin support and one-step files**

Update `features/steps/support/lab_checks.py` keys and methods from Lab 5
Streamlit to Lab 4 Streamlit. Rename specific step files with `git mv`:

```text
the_lab_5_ordinary_network_policy_should_be_empty.py
  -> the_lab_4_ordinary_network_policy_should_be_empty.py
the_lab_5_forward_should_be_loopback_only.py
  -> the_lab_4_forward_should_be_loopback_only.py
lab_5_should_follow_lab_3_without_reusing_its_forward.py
  -> lab_4_should_follow_lab_3_without_invoking_lab_5.py
```

Each file retains one decorator and delegates to one `LabChecks` method. Add
`the_generated_runner_should_default_to_lab_5.py` only after confirming no
existing Then step covers that sentence.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run:

```bash
uv run python -m unittest \
  tests.test_lab4 \
  tests.test_lab4_policy \
  tests.test_lab4_verifier \
  tests.test_streamlit_inference \
  tests.test_sandbox_launchers
PYTHONPATH=src uv run behave features/0004-streamlit.feature
bash -n labs/lab4/*.sh labs/lab5/*.sh
shellcheck labs/lab4/*.sh labs/lab5/*.sh
```

Expected: all selected unit tests and all Streamlit scenarios pass; Bash and
ShellCheck exit zero.

- [ ] **Step 6: Commit the implementation swap**

```bash
git add labs policies src tests test_support features/steps
git commit -m "Renumber Streamlit as Lab 4 and GPU Qwen as Lab 5"
```

---

### Task 3: Update CPU orchestration and generated-runner behavior

**Files:**
- Modify: `infra/remote/run-cpu-labs.sh`
- Modify: `infra/remote/install-runner.sh`
- Modify: `test_support/shell_lab_harness.py`
- Modify: `tests/test_deployment_orchestration.py`
- Modify: `features/steps/support/lab_checks.py`
- Create or rename: matching one-step files under `features/steps/then/`

**Interfaces:**
- Consumes: Task 2 `labs/lab4` and `labs/lab5` paths.
- Produces: CPU event sequence ending `lab4-build`, `lab4-run`, `lab4-verify`; generated GPU default `lab5`.

- [ ] **Step 1: Make the CPU sequence end with Streamlit Lab 4**

Replace the final lifecycle in `infra/remote/run-cpu-labs.sh` with:

```bash
./labs/lab4/build.sh
./labs/lab4/run.sh
./labs/lab4/verify.sh
```

The file must contain no `./labs/lab5/` invocation.

- [ ] **Step 2: Make vLLM select Lab 5 by default**

In `infra/remote/install-runner.sh`, retain explicit support for all labs but
change only the vLLM-active default:

```bash
if systemctl --user is-active --quiet vllm.service 2>/dev/null; then
    lab=lab5
else
    lab=lab3
fi
```

- [ ] **Step 3: Update deterministic orchestration fakes**

In `run_cpu_lab_sequence(...)`, define the CPU lab command map as:

```python
{
    "lab1": ("run", "verify"),
    "lab2": ("configure-host", "run", "verify"),
    "lab3": ("build", "run", "verify"),
    "lab4": ("build", "run", "verify"),
}
```

Add a small helper that executes the generated runner installer with a fake
active `vllm.service`, reads the generated runner, and returns its default lab.
The test must assert `lab5`, not merely search for the string anywhere.

- [ ] **Step 4: Run orchestration tests and Gherkin**

Run:

```bash
uv run python -m unittest tests.test_deployment_orchestration tests.test_sandbox_launchers
PYTHONPATH=src uv run behave features/0003-aws-deployment.feature
```

Expected: unit tests pass and all AWS deployment scenarios pass.

- [ ] **Step 5: Commit orchestration**

```bash
git add infra/remote test_support tests features
git commit -m "Run Labs 1 through 4 on the CPU host"
```

---

### Task 4: Renumber evidence collection and remove stale evidence

**Files:**
- Modify: `scripts/collect-evidence.sh`
- Create: `scripts/collect-gpu-evidence.sh`
- Modify: `tests/test_deployment_orchestration.py`
- Delete: `evidence/cpu/lab5/`
- Delete: current files under `evidence/gpu/`

**Interfaces:**
- Consumes: strict SSH state from `state/cpu-connection.env` and `state/gpu-connection.env`.
- Produces: atomic sanitized `evidence/cpu/lab4/` and `evidence/gpu/` directories with exact artifact sets.

- [ ] **Step 1: Write failing collector tests**

Add assertions that CPU collection uses only Lab 4 paths and that the GPU
collector uses strict host checking, validates safe tar members, requires an
exact four-file set, redacts files individually, and atomically replaces the
destination:

```python
self.assertIn("tar -C evidence/cpu -cf - lab4", self.collect)
self.assertNotIn("evidence/cpu -cf - lab5", self.collect)
self.assertIn("StrictHostKeyChecking=yes", self.collect_gpu)
self.assertIn("expected-gpu-files.txt", self.collect_gpu)
self.assertIn("actual-gpu-files.txt", self.collect_gpu)
self.assertIn("agent-result.json", self.collect_gpu)
self.assertIn("sandbox-create.log", self.collect_gpu)
self.assertIn("gpus.txt", self.collect_gpu)
self.assertIn("policy.json", self.collect_gpu)
```

Run `uv run python -m unittest tests.test_deployment_orchestration` and expect
failure because the new paths and GPU collector do not yet exist.

- [ ] **Step 2: Rename CPU evidence collection to Lab 4**

In `scripts/collect-evidence.sh`, rename all scoped variables, archive members,
temporary paths, diagnostics, staging directories, and destinations from Lab 5
to Lab 4. Preserve the exact 11-file Streamlit artifact list and the existing
safe-member, symlink, redaction, and atomic-replacement checks.

- [ ] **Step 3: Implement bounded GPU evidence collection**

Create `scripts/collect-gpu-evidence.sh` with `set -euo pipefail`. It must:

1. source `infra/aws/gpu-lib.sh` and require `state/gpu-connection.env`;
2. use the repository `state/gpu-known_hosts` with strict host checking;
3. stream `tar -C evidence -cf - gpu` from the GPU host into a private temporary directory;
4. reject absolute paths, `..`, out-of-scope members, symlinks, and non-regular extracted content;
5. require exactly `agent-result.json`, `gpus.txt`, `policy.json`, and `sandbox-create.log`;
6. redact OpenAI/AWS/Authorization patterns from each file separately;
7. stage under `evidence/.gpu-stage.XXXXXX` on the repository filesystem;
8. replace `evidence/gpu` through a recoverable same-filesystem rename sequence.

Never call `openshell provider get`, `printenv`, or print credential values.

- [ ] **Step 4: Delete old-numbered acceptance evidence**

After confirming the exact paths with `git status --short`, remove only:

```text
evidence/cpu/lab5/
evidence/gpu/agent-result.json
evidence/gpu/gpus.txt
evidence/gpu/policy.json
```

Do not delete `evidence/cpu/lab3` or the CPU report evidence.

- [ ] **Step 5: Verify collectors**

Run:

```bash
uv run python -m unittest tests.test_deployment_orchestration
bash -n scripts/collect-evidence.sh scripts/collect-gpu-evidence.sh
shellcheck scripts/collect-evidence.sh scripts/collect-gpu-evidence.sh
./scripts/scan-secrets.sh .
git diff --check
```

Expected: all commands exit zero and the secret scan reports clean.

- [ ] **Step 6: Commit evidence migration**

```bash
git add scripts tests evidence/cpu/lab5 evidence/gpu
git commit -m "Migrate acceptance evidence to the new lab ordering"
```

---

### Task 5: Rewrite workshop guidance around the CPU-first progression

**Files:**
- Modify: `README.md`
- Modify: `labs/lab4/README.md`
- Modify: `labs/lab5/README.md`
- Modify: `docs/openshell-why-it-matters.md`
- Modify: `docs/evidence-index.md`
- Modify: `docs/troubleshooting.md`
- Modify if labels exist: `diagrams/openshell-ai-application-workflow.excalidraw`
- Regenerate if source changed: `diagrams/openshell-ai-application-workflow.svg`
- Modify: `docs/superpowers/specs/2026-08-18-openshell-four-lab-design.md`
- Modify: `docs/superpowers/plans/2026-08-18-openshell-four-lab-implementation.md`
- Modify: `docs/superpowers/specs/2026-09-14-openshell-lab5-streamlit-design.md`
- Modify: `docs/superpowers/plans/2026-09-14-openshell-lab5-streamlit.md`
- Modify: `tests/test_lab4.py`

**Interfaces:**
- Consumes: final paths and identities from Tasks 2 through 4.
- Produces: one unambiguous public workshop sequence and accurate current/pending evidence claims.

- [ ] **Step 1: Write failing documentation assertions**

In `tests/test_lab4.py`, require all public guidance to contain the new
Streamlit identities and reject the old ones:

```python
self.assertIn("Labs 1–4", root_readme)
self.assertIn("Lab 5: Qwen/vLLM GPU host", root_readme)
self.assertIn("ssh -N -L 8501:127.0.0.1:18401", root_readme)
self.assertNotIn("Labs 1–3 and 5", root_readme)
self.assertNotIn("openshell-lab5-forward.service", streamlit_runbook)
self.assertIn("openshell-lab4-forward.service", streamlit_runbook)
```

Run `uv run python -m unittest tests.test_lab4` and expect documentation
assertion failures.

- [ ] **Step 2: Update public documentation**

Rewrite the root overview and commands so:

- Labs 1 through 4 are the CPU-host sequence;
- Lab 4 is protected Streamlit on port `18401`;
- Lab 5 is the optional, expensive, capacity-sensitive GPU host;
- the CPU runner examples use `lab4` and GPU examples use `lab5`;
- cleanup commands target the new sandbox and service names;
- the evidence index points to `evidence/cpu/lab4` and identifies GPU evidence
  as current only after successful Task 8 acceptance.

Update both lab runbooks and the why-it-matters narrative consistently. Add
the one-time existing-host cleanup commands from the design.

- [ ] **Step 3: Mark historical plans as superseded**

At the top of each listed 2026-08-18 or 2026-09-14 historical plan/spec, add:

```markdown
> **Numbering note:** This is a historical implementation record. The current
> workshop numbering is defined by
> `docs/superpowers/specs/2026-09-16-renumber-streamlit-lab4-gpu-lab5-design.md`:
> Streamlit is Lab 4 and GPU Qwen is Lab 5.
```

Do not mechanically rewrite historical decision narratives.

- [ ] **Step 4: Update diagrams only if lab-number labels are present**

Run:

```bash
rg -n 'Lab 4|Lab 5|lab4|lab5' diagrams
```

If no match is returned, make no diagram change. If labels are present, update
the editable Excalidraw source first and regenerate the SVG with the existing
repository workflow; never edit only the rendered SVG.

- [ ] **Step 5: Verify documentation and commit**

Run:

```bash
uv run python -m unittest tests.test_lab4
rg -n 'Labs 1–3 and 5|Lab 5: protected Streamlit|Lab 4: Qwen/vLLM' \
  README.md labs docs/openshell-why-it-matters.md docs/evidence-index.md
./scripts/scan-secrets.sh .
git diff --check
```

Expected: the unit test passes; the obsolete-public-wording search returns no
matches outside explicitly marked historical documents; secret scan and diff
check exit zero.

Commit:

```bash
git add README.md labs docs diagrams tests
git commit -m "Document the CPU-first five-lab progression"
```

---

### Task 6: Run complete local acceptance and commit-addressed build checks

**Files:**
- Verify only: repository-wide tracked files

**Interfaces:**
- Consumes: all local implementation and documentation commits.
- Produces: one clean commit-addressed tree eligible for remote deployment.

- [ ] **Step 1: Audit active numbering**

Run scoped searches and inspect every match:

```bash
rg -n --hidden --glob '!\.git/**' \
  'Lab 4|Lab 5|lab4|lab5|openshell-lab4|openshell-lab5|18401|18501' .
```

Expected: `18501` appears only in historical notes if needed; all active
Streamlit matches use Lab 4 and all active GPU matches use Lab 5.

- [ ] **Step 2: Run full local verification**

Run:

```bash
./scripts/verify-all.sh
```

Expected: unit tests, all Behave features, EARS audit, shell syntax,
ShellCheck, YAML loading, diagram validation, secret scan, and diff check pass.

- [ ] **Step 3: Verify repository state**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: clean status and the renumbering commits at HEAD. Do not start remote
acceptance from a dirty tree because Streamlit image tags are commit-addressed.

---

### Task 7: Retest Labs 1 through 4 on the CPU host

**Files:**
- Generate: `state/cpu-connection.env` and `state/known_hosts` (gitignored)
- Generate and collect: `evidence/cpu/lab4/`
- Refresh: other bounded CPU evidence produced by the existing collector

**Interfaces:**
- Consumes: committed local tree, persisted OpenShell provider configuration, guarded CPU instance.
- Produces: remotely verified Labs 1 through 4 and current sanitized Lab 4 evidence.

- [ ] **Step 1: Start and validate the guarded CPU host**

Run:

```bash
./infra/aws/start-cpu.sh
```

The script must validate the managed CPU instance tags and exact `t3.micro`.
Refresh `state/known_hosts` through the same `ssh-keyscan` and strict-checking
pattern used by `scripts/deploy-cpu.sh`.

- [ ] **Step 2: Synchronize only approved repository content**

Use the exact `rsync` exclusions from `scripts/deploy-cpu.sh`: `.env*`,
`state/`, private keys, `.venv/`, model caches, model weights, raw evidence,
and raw results. Require strict known-host checking.

- [ ] **Step 3: Check persisted inference configuration without exposing it**

Over SSH, run:

```bash
openshell --version
openshell inference get
```

Require the existing `openai-gpt55` route and model `gpt-5.5`. Do not run
`openshell provider get`, request a stored key, or print environment secrets.
If the persisted route is absent, stop the CPU instance and ask the user to
re-enter the provider credential through the existing secure deployment path.

- [ ] **Step 4: Remove only the legacy Streamlit runtime**

After confirming the exact names, stop `openshell-lab5-forward.service` if it
exists and delete `openshell-lab5` only when it is the prior Streamlit sandbox.
Do not use wildcard sandbox deletion.

- [ ] **Step 5: Run all CPU labs**

Over strict SSH:

```bash
cd "$HOME/git/openshell-lab"
./infra/remote/run-cpu-labs.sh
./scripts/scan-secrets.sh .
```

Expected: Labs 1, 2, 3, and 4 each report successful verification; the final
Streamlit output names `openshell-lab4` and loopback port `18401`.

- [ ] **Step 6: Verify browser access through the operator tunnel**

Create a temporary local tunnel with exact process ownership:

```bash
ssh -N -L 8501:127.0.0.1:18401 \
  -i "$SSH_KEY_PATH" \
  -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$PWD/state/known_hosts" \
  "$SSH_USER@$PUBLIC_IP"
```

Request `http://127.0.0.1:8501/_stcore/health`, require body `ok`, and stop only
the captured tunnel process.

- [ ] **Step 7: Collect, inspect, and commit CPU evidence**

Run:

```bash
./scripts/collect-evidence.sh
find evidence/cpu/lab4 -maxdepth 1 -type f -print | sort
./scripts/scan-secrets.sh .
git diff --check
```

Require the exact 11-file Lab 4 set. Commit only sanitized evidence:

```bash
git add evidence/cpu docs/evidence-index.md
git commit -m "Record Lab 4 CPU acceptance evidence"
```

- [ ] **Step 8: Stop and verify the CPU host**

Run even when any earlier remote step fails:

```bash
./infra/aws/stop-cpu.sh
```

Then use `infra/aws/lib.sh` under Bash to validate the project tags and require
`instance_state "$INSTANCE_ID"` to return exactly `stopped`.

---

### Task 8: Attempt and retest GPU Lab 5

**Files:**
- Generate: `state/gpu-connection.env` and `state/gpu-known_hosts` (gitignored)
- Generate and collect on success: `evidence/gpu/`
- Modify after result: `docs/evidence-index.md`

**Interfaces:**
- Consumes: committed Lab 5 GPU scripts, exact guarded GPU instance, existing model/driver caches.
- Produces: either current Lab 5 GPU acceptance evidence or an accurate capacity-pending record.

- [ ] **Step 1: Attempt the exact guarded GPU start**

Run:

```bash
./infra/aws/start-gpu.sh
```

If EC2 returns `InsufficientInstanceCapacity`, do not create or resize any
instance. Confirm the guarded GPU remains `stopped`, update the evidence index
to state that Lab 5 remote validation is pending capacity, and proceed to Task
9. Any other failure is diagnosed with `superpowers:systematic-debugging`.

- [ ] **Step 2: Refresh strict GPU SSH identity and synchronize the repository**

When the start succeeds, obtain the public address from the guarded state file,
write `state/gpu-known_hosts` through `ssh-keyscan`, and use strict checking for
all SSH/rsync calls. Apply the same repository exclusions used for CPU deploy.

- [ ] **Step 3: Confirm the four-GPU topology and vLLM readiness**

Run on the GPU host:

```bash
cd "$HOME/git/openshell-lab"
./infra/remote/bootstrap-rhel10.sh
./labs/lab2/configure-host.sh
./labs/lab5/configure-vllm.sh
./labs/lab5/detect-gpu-profile.sh
curl --fail http://127.0.0.1:8000/v1/models
```

Require exactly four homogeneous L4 or four homogeneous L40S devices, the
Qwen model response, and the profile-specific concurrency limit. Do not proceed
on mixed, unsupported, or incomplete topology.

- [ ] **Step 4: Migrate the old sandbox and run Lab 5**

After confirming `openshell-lab4` is the old GPU sandbox, stop only its port
`18080` forward and delete that sandbox. Then run:

```bash
./labs/lab5/configure-openshell.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
./scripts/scan-secrets.sh .
```

Expected: Qwen tool calling succeeds, filesystem and ordinary-network denials
pass, the published report is nonempty, and the verifier reports Lab 5.

- [ ] **Step 5: Collect and commit current GPU evidence**

From the local repository run:

```bash
./scripts/collect-gpu-evidence.sh
find evidence/gpu -maxdepth 1 -type f -print | sort
./scripts/scan-secrets.sh .
git diff --check
```

Require exactly `agent-result.json`, `gpus.txt`, `policy.json`, and
`sandbox-create.log`. Update `docs/evidence-index.md` to describe current Lab 5
acceptance and commit:

```bash
git add evidence/gpu docs/evidence-index.md
git commit -m "Record Lab 5 GPU acceptance evidence"
```

- [ ] **Step 6: Stop and verify the GPU host**

Run even when any earlier GPU step fails:

```bash
./infra/aws/stop-gpu.sh
```

Use `infra/aws/gpu-lib.sh` under Bash to validate the exact instance identity
and require `gpu_field State.Name` to return exactly `stopped`.

---

### Task 9: Independent review, final verification, and handoff

**Files:**
- Verify: all tracked files and final evidence
- Modify only if review finds an issue: affected implementation, scenarios, tests, or docs

**Interfaces:**
- Consumes: complete renumbering and available remote acceptance evidence.
- Produces: reviewed, clean, locally committed `main` ready for an explicit push request.

- [ ] **Step 1: Request independent read-only review**

Use `superpowers:requesting-code-review` and ask the reviewer to compare the
implementation with the approved spec. Require specific attention to:

- no reversed or ambiguous Lab 4/Lab 5 references;
- CPU runner excluding GPU Lab 5;
- vLLM default selecting Lab 5;
- Streamlit provider/credential boundary;
- loopback-only port `18401`;
- GPU guardrails and unchanged validated topology;
- exact, sanitized, non-stale evidence;
- both AWS instances stopped.

Resolve every Critical and Important finding through EARS/TDD before continuing.

- [ ] **Step 2: Run final full verification**

Run fresh:

```bash
./scripts/verify-all.sh
git status --short
```

Expected: the full suite exits zero and status is clean. If a capacity outcome
changed documentation or evidence after the prior commit, verify and commit
that bounded update before rerunning this step.

- [ ] **Step 3: Confirm remote and AWS terminal state**

Run:

```bash
git log --oneline -12
git rev-list --left-right --count origin/main...HEAD
```

Query both guarded EC2 instances read-only and require `stopped`. Report whether
the commits remain local or have been pushed; do not push without explicit user
authorization.

- [ ] **Step 4: Finish the branch**

Use `superpowers:finishing-a-development-branch`. This repository is expected
to remain the normal `main` checkout selected by the user; preserve it and
offer only the applicable integration action.
