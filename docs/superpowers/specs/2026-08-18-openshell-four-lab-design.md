# OpenShell Four-Lab Demonstration Design

## Purpose

Build a repeatable four-lab demonstration that starts with remote OpenAI inference and GitHub-only agent egress, adds filesystem confinement, packages the application in a Podman image, and finishes with the same application using local Qwen inference through vLLM.

The repository root is `/Users/rcook/git/openshell-lab`. The deployed source root is `/home/ec2-user/openshell-lab`. No credential, token, private key, generated provider database, or unredacted environment file may enter Git history or a GitHub push.

## Demonstration Narrative

The labs change one security or infrastructure boundary at a time:

1. OpenShell restricts ordinary agent egress to public GitHub API reads while deliberately applying no Landlock filesystem rules.
2. The same application gains fail-closed filesystem enforcement and can write only to `/var/www/html` inside the sandbox, which maps to a dedicated host publication directory.
3. The application becomes an immutable, non-root Podman image and demonstrates both denied and allowed GitHub access under OpenShell.
4. The same image and agent workflow move from OpenAI-managed inference to the previously validated Qwen/vLLM GPU deployment.

The report target is the public NVIDIA OpenShell repository. Every successful report describes the five most recent merged pull requests, related issues or task groupings, labels, authors, timestamps, and useful evidence-backed summaries. The report must distinguish missing metadata from negative findings instead of inventing associations.

## Deployment Topology

### CPU host for Labs 1–3

- AWS Region: `us-east-1`
- AMI: `ami-00adafae70b8029d8`
- Verified AMI identity: RHEL 10.2 x86_64, EBS-backed
- Instance type: `t3.micro`
- Purchase option: On-Demand
- VPC: default VPC `vpc-a0dceeda`
- Security group: existing `wide` group `sg-052f8b62b8394f363`
- EC2 key pair: `rcook`; local private key remains outside this repository
- Operating user: `ec2-user`
- Runtime: rootless Podman 5.x and the OpenShell RPM systemd user service

The bootstrap creates a bounded swap file because RHEL, Podman, OpenShell, and the application must coexist within 1 GiB RAM. The bootstrap must be idempotent and must not place secrets in EC2 user data, shell history, process arguments, logs, or repository files.

### GPU host for Lab 4

Reuse the stopped validated instance unless the operator explicitly supplies a replacement:

- AWS Region: `us-east-2`
- Instance: `i-000d2fc821040d9e3`
- Instance type: `g6e.12xlarge`
- GPU topology: four NVIDIA L40S GPUs with 183,104 MiB aggregate GPU memory
- vLLM model: `Qwen/Qwen3.6-27B`
- Precision: unquantized BF16
- Tensor parallelism: 4
- Maximum model length: 32,768 tokens

The existing GPU host preserves the previously validated driver, model cache, vLLM, and OpenShell state on its EBS volume. Lab automation must inspect and verify that state before changing it.

## Shared Application

The application has two separable responsibilities:

1. A deterministic evidence collector invokes `/usr/bin/curl` to make read-only GitHub REST requests. It normalizes pull request, issue, label, and merge evidence into structured JSON. It never asks the model to invent or retrieve evidence.
2. A bounded tool-calling agent sends the evidence to the configured OpenAI-compatible Chat Completions endpoint and validates the returned Markdown. It limits tool iterations, request time, response size, and report structure.

The model-facing tool loop uses the same OpenAI-compatible request contract for remote OpenAI and local vLLM. The application addresses OpenShell-managed inference at `https://inference.local/v1`; it never receives the provider's actual base URL or API key.

The default remote model identifier is `gpt-5.5`. Deployment validates that the configured OpenAI account exposes that identifier before setting the route. If it is unavailable, deployment stops and reports the account-visible GPT-5.5 identifiers. It must not silently substitute another model.

Report validation requires:

- exactly five distinct merged pull requests;
- a stable heading and generation timestamp;
- PR number, title, author, merge timestamp, and URL for each entry;
- labels or an explicit statement that no labels were present;
- associated issue/task evidence or an explicit statement that none was found;
- a model summary grounded in collected evidence;
- no credentials, authorization headers, query secrets, or internal provider configuration.

## OpenShell Control Boundaries

### Managed inference

The OpenAI credential is entered interactively after the CPU host is ready. The CLI reads `OPENAI_API_KEY` from the environment without embedding its value in a command. OpenShell stores the credential using its encrypted provider store, and the shell variable is immediately unset.

The sandbox calls `inference.local`, which is distinct from ordinary sandbox egress. The gateway makes the provider request and injects the credential at the trusted boundary. Consequently, the agent's ordinary network policy can contain only GitHub while the model still functions.

### GitHub network policy

The allow policy grants only:

- destination `api.github.com`;
- TCP port 443;
- REST read-only access;
- the exact `/usr/bin/curl` binary shipped in the sandbox image;
- request paths required for public NVIDIA/OpenShell pull request and issue evidence.

The policy does not permit general web browsing, arbitrary GitHub hosts, Git transport, mutation methods, or Python-originated external sockets. Demonstration checks must prove that another host, another binary, and a GitHub mutation request are denied.

No GitHub token is required for the public lab. If rate limiting makes authenticated access necessary, a separately approved OpenShell GitHub provider may be added interactively; its secret must follow the same non-repository handling rules.

### Lab 1 filesystem posture

Lab 1 deliberately disables Landlock filesystem restriction by supplying an explicit filesystem policy with:

- `include_workdir: false`;
- an empty read-only list;
- an empty read-write list.

OpenShell's Linux supervisor treats an empty effective path set as a Landlock no-op. The lab must show this effective policy and label the behavior clearly; omission of the filesystem section is not equivalent because OpenShell defaults the work directory to writable.

Lab 1 writes its report within the sandbox workspace and downloads it through the OpenShell CLI. It does not mount the host web directory.

### Labs 2–4 filesystem posture

These labs recreate the sandbox because filesystem policy is static. The policy:

- reads only the system libraries, certificates, devices, application code, and runtime paths proven necessary by execution;
- writes only `/var/www/html`;
- sets `include_workdir: false`;
- uses `landlock.compatibility: hard_requirement` so unavailable enforcement aborts startup;
- sets `PYTHONDONTWRITEBYTECODE=1` and avoids temporary-file APIs outside the target directory;
- creates atomic report temporary files within `/var/www/html` before rename.

Tests must prove successful report creation and denied writes to `/tmp`, `/sandbox`, `/home`, and `/etc`. No convenience write exception may be added merely to make a test pass.

## Host Publication Design

The source host directory is `/var/www/html/openshell-lab`; it is bind-mounted into the sandbox at `/var/www/html`. OpenShell therefore reasons about the stable in-sandbox path while Podman exposes only the dedicated host subtree.

Host bind mounts are disabled by OpenShell by default. The lab explicitly enables Podman bind mounts in `gateway.toml` and records this security trade-off. The sandbox create request supplies the one reviewed bind mount and its SELinux shared relabel setting. No other host path is exposed.

The generated report is served over HTTP. Publication must work with SELinux enforcing. If direct host Apache access conflicts with the container label, Apache acts as a reverse proxy to a loopback OpenShell-forwarded static server rather than weakening SELinux globally. The validation records the public report URL and fetches it from outside the instance.

## Lab 3 Container Image

The recorded `Containerfile` derives from a pinned, inspected release of `quay.io/aipcc/agentic-ci/openshell`. The implementation resolves and records both a version tag and immutable digest. It must not use an unpinned `latest` reference.

The upstream image currently has no OCI `USER`, so the derived image must:

- install or verify only the required Python and curl runtime dependencies;
- copy application files into a read-only application directory;
- create an explicit unprivileged numeric user and group accepted by OpenShell;
- set the OCI `USER` and a non-writable application working directory;
- direct report output to `/var/www/html` through an explicit argument;
- include image labels identifying the source revision without embedding secrets.

The image build is reproducible through Podman. A deny run and allow run use the same image and static filesystem posture; only the dynamic network policy changes. The deny run must fail on GitHub access, and the allow run must produce a valid five-merge report.

## Lab 4 Local Inference

Lab 4 transfers or rebuilds the reviewed application image on the GPU host and verifies all four GPUs before starting inference. The vLLM server remains a host-managed rootless Podman service and exposes an OpenAI-compatible endpoint only to the host/OpenShell path needed by the provider.

OpenShell configures a provider for the local vLLM URL using a non-secret compatibility value when the client requires an API-key field. The managed inference route changes to `Qwen/Qwen3.6-27B`; the sandbox continues using `inference.local` without code changes.

Validation proves:

- vLLM readiness and the exact served model;
- four-GPU tensor-parallel placement;
- a tool call produced by Qwen and executed by the application;
- the same GitHub-only ordinary egress policy;
- the same report schema and filesystem-write restrictions;
- useful Markdown content rather than a merely syntactically valid file.

## Repository and Secret Hygiene

The repository includes source, policies, test fixtures, specifications, implementation plans, scripts, the Containerfile, operator documentation, and sanitized evidence. It excludes:

- `.env` and credential files;
- SSH keys;
- AWS CLI caches;
- OpenShell gateway state and SQLite databases;
- TLS private keys and provider material;
- Hugging Face caches and model weights;
- generated EC2 connection files containing local key paths;
- raw logs or HTTP captures that may contain authorization data.

Automation writes mutable deployment state beneath a gitignored `state/` directory with owner-only permissions. Every review checkpoint runs tracked-file secret scans and examines staged diffs before any commit. Nothing is pushed automatically.

## Verification Strategy

Behavior is specified first with EARS requirements expressed as Gherkin `Rule` titles. Scenarios cover:

- GitHub-only network allowance and three independent deny proofs;
- Lab 1's explicit filesystem no-op;
- Labs 2–4's sole writable path and denied path matrix;
- deterministic five-merge evidence and Markdown quality;
- immutable non-root image construction;
- secret exclusion and redaction;
- remote OpenAI and local Qwen tool calling;
- AWS launch inputs, idempotent bootstrap, and instance-state handling.

Unit tests mock external HTTP and model calls. Integration tests exercise the built image and policy artifacts. Remote acceptance scripts gather sanitized command output, policy revisions, HTTP status, report hashes, and service state.

OpenCodeReview (`ocr scan`) runs at two checkpoints:

1. after the CPU-host application, policies, image, and runbook pass their automated tests;
2. after GPU/vLLM integration and final documentation are complete.

Each finding is reproduced before changes are made. Accepted corrections update source, tests, documentation, and deployed hosts, followed by the full relevant test suite. Review findings and dispositions are saved without credentials.

## Operator Documentation

The root `README.md` is the manual workshop entry point. It explains prerequisites, cost and shutdown responsibilities, credential prompts, every command for all four labs, expected deny and allow evidence, report URLs, troubleshooting, cleanup, and how to restart stopped instances safely.

Each lab also has a focused README that can be followed independently after shared prerequisites are complete. Commands use placeholders for secrets and discover mutable addresses from gitignored state rather than hard-coding them into tracked files.

## Completion Criteria

The project is complete only when:

1. the RHEL 10 `t3.micro` launches and passes OpenShell health checks;
2. Lab 1 produces a useful report with GitHub-only ordinary egress and demonstrably no Landlock filesystem rules;
3. Lab 2 publishes a report while every tested non-`/var/www/html` write fails;
4. Lab 3 records and builds the pinned non-root Containerfile and proves policy deny/allow behavior;
5. Lab 4 runs that application image against Qwen/vLLM on four L40S GPUs and passes tool-calling, network, filesystem, and report-quality checks;
6. both OpenCodeReview checkpoints are resolved and rerun;
7. the manual documentation reproduces the validated commands;
8. tracked files and commits contain no credentials;
9. sanitized evidence exists for every claimed acceptance result;
10. instance state and ongoing cost are reported explicitly to the operator.
