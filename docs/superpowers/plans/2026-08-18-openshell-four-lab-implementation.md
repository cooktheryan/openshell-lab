# OpenShell Four-Lab Demonstration Implementation Plan

> **Superseded Lab 4 implementation target (2026-09-14):** The guarded
> lifecycle now pins `i-0482b1eb41a016cc4`, a four-L4 `g6.12xlarge` in
> `us-east-2a`. Runtime profile detection accepts only four homogeneous L4 or
> L40S GPUs, regenerates NVIDIA CDI, and selects vLLM `--max-num-seqs 16` for
> L4 or `256` for L40S while preserving Qwen3.6-27B BF16, tensor parallel 4,
> and the 32,768-token context. This addendum supersedes the original
> L40S-only Lab 4 tasks below.

> Runtime reconciliation (2026-08-18): the executed RHEL 10 deployment showed
> that proxy mode always enriches filesystem policy with an enforced Landlock
> baseline. Labs therefore retain writable `/tmp` and `/dev/null`, Lab 1 also
> includes its uploaded workdir, and persistent publication remains limited to
> `/var/www/html` in Labs 2–4. Any older step below that expects a zero-rule
> Landlock policy or denied `/tmp` write is superseded by the design document,
> Gherkin scenarios, policy tests, and remote evidence. Lab 4 also uses
> `host.openshell.internal` after a loopback vLLM preflight because the alias is
> injected at the sandbox boundary and cannot be resolved by gateway-side
> provider verification.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver and validate four reproducible OpenShell labs covering GitHub-only egress, filesystem confinement, a non-root Podman application image, and Qwen/vLLM managed inference.

**Architecture:** Labs 1–3 run progressively on one RHEL 10 `t3.micro` in `us-east-1`; Lab 4 reuses the validated stopped `g6e.12xlarge` in `us-east-2`. One deterministic Python evidence layer and one bounded OpenAI-compatible tool loop run behind OpenShell, while static filesystem policies and dynamic GitHub network policies provide the demonstrations.

**Tech Stack:** Python 3 standard library, Bash, EARS/Gherkin with Behave, rootless Podman 5, OpenShell RPM/CLI, Linux Landlock, AWS CLI, systemd user services, Apache HTTP Server, vLLM, Qwen3.6-27B, OpenCodeReview.

**Spec:** `docs/superpowers/specs/2026-08-18-openshell-four-lab-design.md`

## Global Constraints

- Work only in `/Users/rcook/git/openshell-lab` locally and `/home/ec2-user/git/openshell-lab` remotely.
- Use RHEL 10 AMI `ami-00adafae70b8029d8`, `t3.micro`, On-Demand, in `us-east-1` for Labs 1–3.
- Default the remote inference model to `gpt-5.5`; verify account availability and never silently substitute another model.
- Permit ordinary sandbox egress only to read-only `api.github.com:443` requests made by `/usr/bin/curl`.
- Lab 1 must apply the proxy-enriched Landlock baseline; Labs 2–4 must restrict persistent writes to `/var/www/html` while retaining `/tmp` and `/dev/null` runtime paths.
- Use `landlock.compatibility: hard_requirement` for Labs 2–4.
- Derive Lab 3 from a versioned, digest-pinned `quay.io/aipcc/agentic-ci/openshell` image and add a non-root OCI user.
- Reuse `i-000d2fc821040d9e3` in `us-east-2` for Lab 4 unless inspection contradicts the validated GPU state.
- Never add credentials, keys, provider databases, TLS private keys, model caches, or unredacted logs to Git.
- Never push automatically. Use Conventional Commits with DCO signoff.
- Run OpenCodeReview after Labs 1–3 and again after Lab 4/documentation.

---

### Task 1: Repository Safety and Executable Requirements

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `features/README.md`
- Create: `features/dashboard.html`
- Create: `features/0001-report-agent.feature`
- Create: `features/0002-openshell-controls.feature`
- Create: `features/0003-aws-deployment.feature`
- Create: `features/environment.py`
- Create: `features/steps/__init__.py`
- Create: `features/steps/given/__init__.py`
- Create: `features/steps/given/the_lab_artifacts_are_available.py`
- Create: `features/steps/when/__init__.py`
- Create: `features/steps/when/the_lab_check_is_performed.py`
- Create: `features/steps/then/__init__.py`
- Create: `features/steps/then/the_lab_check_should_be.py`
- Create: `features/steps/support/lab_checks.py`
- Create: `tests/test_repository_safety.py`
- Create: `scripts/scan-secrets.sh`

**Interfaces:**
- Produces: `features/environment.py` context dictionaries consumed by later Behave steps.
- Produces: `scripts/scan-secrets.sh [ROOT]`, returning zero only when tracked/candidate files contain no banned credential patterns.

- [ ] **Step 1: Install the EARS/Gherkin dashboard and methodology README**

Copy the skill-provided files without modifying their contents:

```bash
cp /Users/rcook/.codex/skills/ears-gherkin-dev/templates/dashboard.html features/dashboard.html
cp /Users/rcook/.codex/skills/ears-gherkin-dev/templates/README.md features/README.md
```

- [ ] **Step 2: Write EARS requirements and declarative scenarios**

Use one `Rule:` per requirement, each containing exactly one `shall`. Cover exactly five merged PRs, useful evidence, GitHub-only egress, the Lab 1 no-op, the Labs 2–4 write-deny matrix, non-root image metadata, remote and local tool calling, AWS launch values, and credential exclusion.

Example rule:

```gherkin
Rule: While filesystem confinement is enabled, the report agent shall write only beneath /var/www/html.

  Scenario Outline: A non-publication write is denied
    Given filesystem confinement is enabled
    When the agent attempts to write to "<path>"
    Then OpenShell reports that the write was denied

    Examples:
      | path             |
      | /tmp/blocked     |
      | /sandbox/blocked |
      | /home/blocked    |
      | /etc/blocked     |
```

- [ ] **Step 3: Write failing repository-safety tests**

Test `.gitignore` includes `.env*`, `state/`, private keys, OpenShell databases, TLS keys, Hugging Face caches, and evidence raw logs. Test `scan-secrets.sh` detects representative AWS, OpenAI, and private-key markers in a temporary directory while allowing `OPENAI_API_KEY` variable names without assigned values.

- [ ] **Step 4: Run the safety tests and confirm RED**

Run: `uv run python -m unittest tests.test_repository_safety -v`

Expected: failure because `.gitignore` and `scripts/scan-secrets.sh` are absent.

- [ ] **Step 5: Implement `.gitignore`, packaging metadata, and the secret scanner**

The scanner uses `rg` against files returned by `git ls-files --cached --others --exclude-standard`, never prints matched secret values, and reports only filenames and rule names.

- [ ] **Step 6: Run unit tests and the EARS audit**

```bash
uv run python -m unittest tests.test_repository_safety -v
uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py features/
```

Expected: all tests pass and the audit reports no findings.

- [ ] **Step 7: Commit**

```bash
git add .gitignore pyproject.toml features tests/test_repository_safety.py scripts/scan-secrets.sh
git commit --signoff -m "test: specify OpenShell lab behavior"
```

### Task 2: Deterministic GitHub Evidence and Markdown Validation

**Files:**
- Create: `src/openshell_lab/__init__.py`
- Create: `src/openshell_lab/github_evidence.py`
- Create: `src/openshell_lab/report.py`
- Create: `tests/fixtures/github/pulls.json`
- Create: `tests/fixtures/github/issues.json`
- Create: `tests/test_github_evidence.py`
- Create: `tests/test_report.py`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Produces: `select_recent_merges(pulls: list[dict], limit: int = 5) -> list[dict]`.
- Produces: `extract_issue_numbers(body: str, pr_number: int, limit: int = 5) -> list[int]`.
- Produces: `collect_evidence(curl_bin: str = "/usr/bin/curl") -> dict`.
- Produces: `validate_markdown(markdown: str, evidence: dict) -> str`.
- Produces: `write_report(path: pathlib.Path, markdown: str) -> None`, creating and renaming its temporary file in the destination directory.

- [ ] **Step 1: Write failing evidence-selection tests**

Cover descending `merged_at` order, exclusion of closed-unmerged PRs, exactly-five enforcement, de-duplicated explicit issue references, bounded bodies, labels, milestones, and pull-request-versus-issue classification.

- [ ] **Step 2: Run evidence tests and confirm RED**

Run: `uv run python -m unittest tests.test_github_evidence -v`

Expected: import failure for `openshell_lab.github_evidence`.

- [ ] **Step 3: Implement deterministic evidence collection**

Invoke curl with `--silent --show-error --fail-with-body --max-time 30 --max-filesize 8388608`, GitHub API version `2022-11-28`, and fixed `https://api.github.com/repos/NVIDIA/OpenShell/...` URLs. Reject non-JSON, oversized, non-list pull responses, and any selected entry without `merged_at`.

- [ ] **Step 4: Write failing Markdown tests**

Require the exact title, one executive summary, exactly five ordered PR headings, per-PR merged/author/label/issue fields, HTTPS evidence links, deterministic evidence index, and rejection of authorization headers or strings matching credential patterns.

- [ ] **Step 5: Implement report validation and atomic writing**

Use `tempfile.NamedTemporaryFile(dir=path.parent, delete=False)`, `os.fsync`, mode `0600`, and `os.replace`. Do not call `tempfile` without the destination directory.

- [ ] **Step 6: Run unit tests and scenarios**

```bash
uv run python -m unittest tests.test_github_evidence tests.test_report -v
uvx --from behave behave features/0001-report-agent.feature
```

Expected: all tests and scenarios pass.

- [ ] **Step 7: Commit**

```bash
git add src tests features/steps
git commit --signoff -m "feat: collect merge evidence and validate reports"
```

### Task 3: Bounded OpenAI-Compatible Tool Agent

**Files:**
- Create: `src/openshell_lab/tool_agent.py`
- Create: `src/openshell_lab/cli.py`
- Create: `tests/test_tool_agent.py`
- Create: `tests/test_cli.py`
- Modify: `pyproject.toml`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Produces: `build_chat_request(messages: list[dict]) -> dict`, deliberately omitting provider model and credentials.
- Produces: `dispatch_tool(name: str, arguments: dict, state: ToolState) -> dict`.
- Produces: `run_tool_loop(report_path: pathlib.Path, curl_bin: str = "/usr/bin/curl", max_tool_calls: int = 16) -> dict`.
- Produces CLI: `openshell-lab-report --output PATH`; the executable remains pinned to `/usr/bin/curl`.

- [ ] **Step 1: Write failing tool-loop tests**

Simulate model responses for `list_recent_merges`, `inspect_pull_request`, `inspect_linked_issue`, and `write_report`. Verify selected-set bounds, explicit-link-only issue inspection, malformed JSON rejection, 16-call limit, 8 MiB response limit, 2 MiB tool-result limit, and recoverable report-validation retry.

- [ ] **Step 2: Run tool-agent tests and confirm RED**

Run: `uv run python -m unittest tests.test_tool_agent tests.test_cli -v`

Expected: import failures for the new modules.

- [ ] **Step 3: Implement the bounded tool loop**

POST only to `https://inference.local/v1/chat/completions`. Use tool choice `auto`, temperature `0.2`, maximum output tokens `1800`, and a system prompt that requires evidence-grounded statements. A successful run must end through `write_report`; plain assistant text is not success.

- [ ] **Step 4: Implement the CLI**

The CLI resolves the output path, refuses a directory, runs the tool loop, emits only sanitized JSON status, and returns nonzero on policy, transport, validation, or premature-model completion errors.

- [ ] **Step 5: Run unit and behavior tests**

```bash
uv run python -m unittest tests.test_tool_agent tests.test_cli -v
uvx --from behave behave features/0001-report-agent.feature
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/openshell_lab/tool_agent.py src/openshell_lab/cli.py tests pyproject.toml features/steps
git commit --signoff -m "feat: add bounded merge-report tool agent"
```

### Task 4: AWS Lifecycle and RHEL 10 Bootstrap

**Files:**
- Create: `infra/aws/launch-cpu.sh`
- Create: `infra/aws/describe-cpu.sh`
- Create: `infra/aws/stop-cpu.sh`
- Create: `infra/aws/start-cpu.sh`
- Create: `infra/aws/lib.sh`
- Create: `infra/remote/bootstrap-rhel10.sh`
- Create: `tests/test_aws_scripts.py`
- Create: `tests/test_bootstrap_scripts.py`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Produces: `state/cpu-connection.env` with non-secret region, instance ID, IPs, subnet, and an SSH-key path reference; mode `0600`, gitignored.
- Produces: `infra/aws/launch-cpu.sh`, returning the instance ID on stdout after both EC2 status checks pass.
- Produces: idempotent `infra/remote/bootstrap-rhel10.sh` for execution as `ec2-user`.

- [ ] **Step 1: Write failing static AWS tests**

Assert exact region, AMI, instance type, On-Demand behavior, default VPC lookup, `wide` security-group lookup, `rcook` key pair, IMDSv2 requirement, encrypted gp3 root volume, project tags, and absence of credentials in user data.

- [ ] **Step 2: Run AWS tests and confirm RED**

Run: `uv run python -m unittest tests.test_aws_scripts tests.test_bootstrap_scripts -v`

Expected: failures because scripts do not exist.

- [ ] **Step 3: Implement lifecycle scripts**

Resolve every mutable AWS identifier through read-only AWS CLI calls. Validate resolved values before mutation. Launch exactly one instance, wait for `instance-running` and `instance-status-ok`, and atomically write state. Stop scripts validate the project tag before stopping and never terminate an instance.

- [ ] **Step 4: Implement idempotent bootstrap**

Bootstrap must install RHEL packages `podman`, `curl`, `httpd`, `python3`, `git`, `jq`, `policycoreutils-python-utils`, and `firewalld`; create a 2 GiB root-owned `0600` swap file only when absent; enable linger and rootless `podman.socket`; install OpenShell through the official install script; pin Podman in `gateway.toml`; and verify `openshell status` plus `openshell whoami`.

- [ ] **Step 5: Run script tests and ShellCheck when available**

```bash
uv run python -m unittest tests.test_aws_scripts tests.test_bootstrap_scripts -v
for script in infra/aws/*.sh infra/remote/*.sh; do bash -n "$script"; done
if command -v shellcheck >/dev/null; then shellcheck infra/aws/*.sh infra/remote/*.sh; fi
```

Expected: all checks pass.

- [ ] **Step 6: Commit**

```bash
git add infra tests features/steps
git commit --signoff -m "feat: automate RHEL OpenShell host lifecycle"
```

### Task 5: Lab 1 GitHub-Only Policy with Filesystem No-Op

**Files:**
- Create: `policies/lab1-github-only-no-filesystem.yaml`
- Create: `labs/lab1/configure-openai.sh`
- Create: `labs/lab1/run.sh`
- Create: `labs/lab1/verify.sh`
- Create: `labs/lab1/README.md`
- Create: `tests/test_lab1.py`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Consumes: `openshell-lab-report`, OpenShell CLI, and runtime `OPENAI_API_KEY`.
- Produces: sandbox `openshell-lab1` and downloaded `evidence/lab1/nvidia-openshell-last-5-merges.md`.

- [ ] **Step 1: Write failing Lab 1 artifact tests**

Parse YAML and verify `version: 1`, `include_workdir: false`, empty filesystem lists, only `api.github.com:443`, REST read-only enforcement, and only `/usr/bin/curl`. Verify scripts never contain an assigned OpenAI credential.

- [ ] **Step 2: Run Lab 1 tests and confirm RED**

Run: `uv run python -m unittest tests.test_lab1 -v`

Expected: missing artifacts.

- [ ] **Step 3: Generate the policy and scripts**

`configure-openai.sh` requires `OPENAI_API_KEY` in its environment, creates or updates provider `openai-gpt55` using a bare credential key, validates `gpt-5.5`, configures managed inference, unsets the variable, and prints sanitized route state. `run.sh` creates/recreates the sandbox with the policy, uploads the package, runs the report CLI in `/sandbox`, then downloads the report.

- [ ] **Step 4: Implement deny and no-op verification**

`verify.sh` proves GitHub GET succeeds, `example.com` fails, Python direct egress fails, GitHub POST fails, arbitrary workspace and `/tmp` writes succeed, and OCSF/log evidence shows no Landlock rules applied.

- [ ] **Step 5: Run tests and policy parsing**

```bash
uv run python -m unittest tests.test_lab1 -v
uv run python -c 'import yaml; yaml.safe_load(open("policies/lab1-github-only-no-filesystem.yaml"))'
bash -n labs/lab1/*.sh
```

Expected: all checks pass.

- [ ] **Step 6: Commit**

```bash
git add policies labs/lab1 tests/test_lab1.py features/steps
git commit --signoff -m "feat: add GitHub-only no-filesystem lab"
```

### Task 6: Lab 2 Filesystem Confinement and HTTP Publication

**Files:**
- Create: `policies/lab2-webroot-only.yaml`
- Create: `labs/lab2/configure-host.sh`
- Create: `labs/lab2/run.sh`
- Create: `labs/lab2/verify.sh`
- Create: `labs/lab2/README.md`
- Create: `infra/remote/openshell-lab-httpd.conf`
- Create: `tests/test_lab2.py`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Produces: host directory `/var/www/html/openshell-lab`, sandbox `openshell-lab2`, loopback report service, and an externally fetchable Markdown URL.

- [ ] **Step 1: Write failing filesystem-policy tests**

Verify the only `read_write` entry is `/var/www/html`, `include_workdir` is false, Landlock is `hard_requirement`, required runtime paths are read-only, and the Podman driver config exposes only host `/var/www/html/openshell-lab` at sandbox `/var/www/html`.

- [ ] **Step 2: Run Lab 2 tests and confirm RED**

Run: `uv run python -m unittest tests.test_lab2 -v`

Expected: missing artifacts.

- [ ] **Step 3: Implement host preparation and publication**

Enable `enable_bind_mounts = true` only in `[openshell.drivers.podman]`, restart the gateway, create the dedicated host directory owned by `ec2-user`, preserve SELinux enforcing, and configure Apache to reverse proxy a loopback OpenShell forward when direct static access is not label-compatible.

- [ ] **Step 4: Implement sandbox creation and report generation**

Create the sandbox with one reviewed bind mount using `--driver-config-json`, upload the package, set `PYTHONDONTWRITEBYTECODE=1`, write the report to `/var/www/html/nvidia-openshell-last-5-merges.md`, and start a loopback read-only static server without writing outside the webroot.

- [ ] **Step 5: Implement deny-matrix verification**

Verify report creation succeeds and `touch` fails at `/tmp/blocked`, `/sandbox/blocked`, `/home/blocked`, and `/etc/blocked`. Verify the externally fetched report hash matches the host file and the Markdown validator accepts it.

- [ ] **Step 6: Run tests and behavior scenarios**

```bash
uv run python -m unittest tests.test_lab2 -v
uvx --from behave behave features/0002-openshell-controls.feature
bash -n labs/lab2/*.sh
```

Expected: all local artifact checks pass.

- [ ] **Step 7: Commit**

```bash
git add policies labs/lab2 infra/remote/openshell-lab-httpd.conf tests/test_lab2.py features/steps
git commit --signoff -m "feat: confine report writes to the web root"
```

### Task 7: Lab 3 Pinned Non-Root Application Image and Policy Deny/Allow

**Files:**
- Create: `container/Containerfile`
- Create: `container/resolve-base.sh`
- Create: `container/base-image.lock`
- Create: `policies/lab3-network-deny.yaml`
- Create: `policies/lab3-github-allow.yaml`
- Create: `labs/lab3/build.sh`
- Create: `labs/lab3/run.sh`
- Create: `labs/lab3/verify.sh`
- Create: `labs/lab3/README.md`
- Create: `tests/test_container.py`
- Create: `tests/test_lab3.py`

**Interfaces:**
- Produces image `localhost/openshell-lab-agent:<git-short-sha>` with numeric non-root OCI user.
- Produces sandbox `openshell-lab3` and a policy revision history containing a denied run followed by an allowed run.

- [ ] **Step 1: Write failing image and policy tests**

Verify a version tag and sha256 digest are locked, `FROM` uses the digest, the image defines non-root `USER`, application files are outside `/var/www/html`, no credential is copied, both Lab 3 policies retain the Lab 2 static posture, deny has no network rules, and allow has only the GitHub curl rule.

- [ ] **Step 2: Run Lab 3 tests and confirm RED**

Run: `uv run python -m unittest tests.test_container tests.test_lab3 -v`

Expected: missing artifacts.

- [ ] **Step 3: Resolve and record the upstream image**

Use `skopeo inspect` on the newest stable `0.3.x` tag, record name/tag/digest/created/architecture in `base-image.lock`, and use the immutable digest in `Containerfile`. Reject development tags and mutable `latest`.

- [ ] **Step 4: Implement the Containerfile and build script**

Install only Python and curl dependencies, copy `src/openshell_lab`, create UID/GID 1500, set `USER 1500:1500`, set `PYTHONDONTWRITEBYTECODE=1`, and use the report CLI as entrypoint. Build with Podman and inspect `.Config.User` before success.

- [ ] **Step 5: Implement deny/allow execution**

Create the image-backed sandbox with the reviewed webroot bind and deny policy, prove report generation fails on GitHub, hot-set the allow policy with `--wait`, prove generation succeeds, and retain policy revision evidence.

- [ ] **Step 6: Run local checks**

```bash
uv run python -m unittest tests.test_container tests.test_lab3 -v
bash -n container/*.sh labs/lab3/*.sh
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add container policies/lab3-* labs/lab3 tests/test_container.py tests/test_lab3.py
git commit --signoff -m "feat: package the report agent as a non-root image"
```

### Task 8: CPU Host Deployment and First OpenCodeReview Gate

**Files:**
- Create: `scripts/deploy-cpu.sh`
- Create: `scripts/collect-evidence.sh`
- Create: `review/run-ocr.sh`
- Create: `review/README.md`
- Create: `review/cpu-findings.md`
- Create: `tests/test_deployment_orchestration.py`
- Modify: source, tests, policies, and docs only for reproduced review findings.

**Interfaces:**
- Produces sanitized `evidence/cpu/` results and `review/cpu-findings.md` dispositions.

- [ ] **Step 1: Write failing orchestration tests**

Verify deployment order is launch, SSH readiness, rsync with excludes, bootstrap, credential pause, Lab 1, Lab 2, Lab 3, secret scan, and evidence collection. Verify errors stop the pipeline and the credential step cannot run without a TTY or pre-set environment value.

- [ ] **Step 2: Implement orchestration and evidence collection**

Use strict SSH host-key handling with a repository-specific known-hosts file under gitignored state. Collect only service states, versions, policies, hashes, sanitized logs, deny exit codes, and report files.

- [ ] **Step 3: Run all local tests before AWS mutation**

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -v
uvx --from behave behave features
uv run python /Users/rcook/.codex/skills/ears-gherkin-dev/scripts/audit.py features/
./scripts/scan-secrets.sh .
```

Expected: all checks pass.

- [ ] **Step 4: Launch and bootstrap the CPU host**

Run `infra/aws/launch-cpu.sh`, upload the repository, run bootstrap, and confirm OpenShell gateway, Podman socket, Apache, swap, SELinux, and firewalld states.

- [ ] **Step 5: Pause for the OpenAI credential**

Ask the operator to export `OPENAI_API_KEY` in the remote interactive shell. Configure the provider without echoing the value, validate `gpt-5.5`, unset the variable, and rescan remote tracked files before proceeding.

- [ ] **Step 6: Run and validate Labs 1–3 remotely**

Execute every run and verify script, fetch the public report externally, collect sanitized evidence, and keep the instance running unless the operator changes the instruction.

- [ ] **Step 7: Run OpenCodeReview and disposition findings**

Use a checksum-verified OpenCodeReview release, run `ocr scan` with a prompt covering security, correctness, policy least privilege, secret handling, and documentation accuracy, record each finding, reproduce it, implement accepted corrections, and rerun all affected tests and remote labs.

- [ ] **Step 8: Commit**

```bash
git add scripts review tests evidence
git commit --signoff -m "test: validate CPU OpenShell labs"
```

### Task 9: Lab 4 Qwen/vLLM GPU Integration

**Files:**
- Create: `infra/aws/start-gpu.sh`
- Create: `infra/aws/stop-gpu.sh`
- Create: `labs/lab4/configure-vllm.sh`
- Create: `labs/lab4/configure-openshell.sh`
- Create: `labs/lab4/run.sh`
- Create: `labs/lab4/verify.sh`
- Create: `labs/lab4/README.md`
- Create: `tests/test_lab4.py`
- Modify: `features/steps/support/lab_checks.py`

**Interfaces:**
- Produces vLLM service for `Qwen/Qwen3.6-27B` at the validated host endpoint.
- Produces provider `qwen36-local`, sandbox `openshell-lab4`, and sanitized `evidence/gpu/`.

- [ ] **Step 1: Write failing GPU artifact tests**

Verify instance ID and region, tag validation before start/stop, four-L40S assertion, BF16, tensor parallel 4, max model length 32768, model name, rootless Podman service, local provider URL, and absence of real credentials.

- [ ] **Step 2: Run Lab 4 tests and confirm RED**

Run: `uv run python -m unittest tests.test_lab4 -v`

Expected: missing artifacts.

- [ ] **Step 3: Implement guarded GPU lifecycle scripts**

Describe the instance and require type `g6e.12xlarge` plus project tags before start or stop. Start, wait for both AWS checks, refresh its connection state, and never terminate it.

- [ ] **Step 4: Implement vLLM and OpenShell configuration**

Inspect existing drivers, service, image, cache, and model before mutation. Configure the exact validated vLLM arguments only when drift exists. Create/update local provider `qwen36-local` with the host-local OpenAI-compatible URL and a documented non-secret compatibility value, then set managed inference to Qwen.

- [ ] **Step 5: Deploy the reviewed application image and run Lab 4**

Transfer the source and locked Containerfile, build or verify the image, create the sandbox with Lab 3 allow policy and webroot-only filesystem posture, and generate the report through Qwen tool calls.

- [ ] **Step 6: Verify GPU and security acceptance**

Check all four GPU UUIDs are active in the vLLM process, exact model readiness, at least one model-generated tool call, GitHub-only egress, denied non-webroot writes, exact five-PR Markdown, and external report retrieval.

- [ ] **Step 7: Run tests and commit**

```bash
uv run python -m unittest tests.test_lab4 -v
uvx --from behave behave features/0002-openshell-controls.feature features/0003-aws-deployment.feature
git add infra/aws labs/lab4 tests/test_lab4.py features/steps evidence/gpu
git commit --signoff -m "feat: run the agent through local Qwen inference"
```

### Task 10: Manual Workshop, Final Review, and Completion Audit

**Files:**
- Create: `README.md`
- Create: `docs/troubleshooting.md`
- Create: `docs/evidence-index.md`
- Create: `review/final-findings.md`
- Create: `scripts/verify-all.sh`
- Modify: every lab README when final commands or findings require correction.

**Interfaces:**
- Produces: complete operator workshop and one-command local verification entry point.

- [ ] **Step 1: Write the manual workshop**

Document prerequisites, AWS costs, exact launch and SSH commands, OpenAI credential entry, all four lab commands, expected denies, expected reports, public URLs, service inspection, persistence locations, troubleshooting, instance stop/start, and cleanup. Use no secret-bearing examples.

- [ ] **Step 2: Implement the final verifier**

`scripts/verify-all.sh` runs unit tests, Behave, the EARS audit, Bash syntax, ShellCheck when available, YAML parsing, Containerfile lock validation, secret scanning, `git diff --check`, and remote acceptance checks when state files identify running instances.

- [ ] **Step 3: Run final OpenCodeReview**

Review the entire tracked repository and sanitized evidence. Reproduce every finding, accept only evidence-backed changes, update tests and remote deployment, and record dispositions in `review/final-findings.md`.

- [ ] **Step 4: Run the complete verification suite**

Run: `./scripts/verify-all.sh`

Expected: every local check passes and every reachable remote lab acceptance check passes.

- [ ] **Step 5: Perform the requirement-by-requirement completion audit**

Map each of the ten design completion criteria to an exact file, test result, remote command output, report hash, policy revision, or review disposition in `docs/evidence-index.md`. Treat absent or indirect evidence as incomplete.

- [ ] **Step 6: Final credential and Git audit**

```bash
./scripts/scan-secrets.sh .
git status --short
git log --show-signature --format=fuller --stat
git remote -v
```

Confirm no push was performed and no ignored secret is staged.

- [ ] **Step 7: Commit**

```bash
git add README.md docs review/final-findings.md scripts/verify-all.sh labs
git commit --signoff -m "docs: publish the validated four-lab workshop"
```
