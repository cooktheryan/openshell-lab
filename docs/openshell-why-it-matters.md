# Why OpenShell matters for AI applications

An AI application becomes materially different when it can call a model,
reach services, and act on files. A non-root container is a sound baseline,
but it does not express which files the application may change, which hosts it
may contact, which privilege-building operations it may attempt, or where its
model credential lives.

OpenShell adds those boundaries as operator-owned policy. This workshop is the
source of truth for the demonstration: the implementation, requirements, and
evidence live in the `openshell-lab` repository.

## The honest baseline: non-root is necessary, not sufficient

Lab 5 does not create a deliberately weak twin of the application. Its image
already runs as numeric UID and GID `1500:1500`, the same basic container
hardening a production team should require. The important question is what a
prompt-injected or malfunctioning non-root process can still do.

Without a narrower runtime boundary, a non-root process can often:

- rewrite files it owns, including its application code;
- read broadly available process and operating-system data;
- connect to any destination permitted by the host network;
- retain a capability bounding set and create new namespaces; and
- receive long-lived credentials through its environment or configuration.

Lab 5 puts the already non-root application inside one protected OpenShell
sandbox, `openshell-lab5`, and verifies each additional boundary. There is no
plain application deployment and no public Streamlit listener to maintain or
accidentally expose.

## The protected data path

The browser reaches Streamlit only through an SSH tunnel and a durable
CPU-host loopback forward. The application reaches the model only through
OpenShell:

```text
browser
  -> local 127.0.0.1:8501
  -> SSH tunnel
  -> CPU host 127.0.0.1:18501
  -> OpenShell service forward
  -> Streamlit in openshell-lab5 on port 8501
  -> https://inference.local/v1/chat/completions
  -> OpenShell-managed openai-gpt55 provider
```

The application request omits model and credential fields. Provider credentials
remain outside the image, environment, filesystem, and request body. OpenShell
selects GPT-5.5 and applies the credential only in its managed inference path.

This is the same model-access pattern used by Labs 1–3. The application code
is portable because it knows the stable `inference.local` contract, not a
provider account, upstream hostname, key, or model deployment detail.

## Four control layers, each with a concrete proof

### Filesystem

**What it protects:** the data and code a compromised application can read or
change.

Lab 5 exposes required operating-system and application paths as read-only.
It grants writes only to `/tmp` and `/dev/null`, with
`landlock.compatibility: hard_requirement`. If the kernel cannot install the
required Landlock rules, sandbox creation fails instead of silently weakening
the policy.

The verifier proves that a write to
`/opt/openshell-lab/lab5-write-denied` fails. This matters even for non-root
software: Unix ownership alone commonly lets an application rewrite its own
files.

### Network

**What it protects:** where application-controlled data can leave.

Lab 5 declares `network_policies: {}`. A Python request to
`https://example.com` must fail, and verification also requires the matching
OpenShell denial event. A failed request without policy evidence is treated as
an operational error, not proof of confinement.

Managed model traffic is deliberately separate. The application calls
`inference.local`, so ordinary internet egress can remain default-deny while
the operator-approved model route works.

### Process

**What it protects:** privilege escalation and kernel isolation primitives.

The policy pins UID and GID `1500`. OpenShell also empties `CapBnd`, sets
`NoNewPrivs=1`, and rejects `unshare -Urn true`. These controls close paths that
remain available in many otherwise non-root containers.

The lesson is not that containers are weak. It is that identity, capability,
and syscall boundaries answer different security questions and should be
verified independently.

### Provider

**What it protects:** model credentials and their authorized use.

The Streamlit application has no provider key, provider hostname, or model
name. It sends bounded chat messages to `inference.local`. OpenShell owns the
`openai-gpt55` provider configured for the CPU labs and performs the upstream
request outside application state.

The verifier checks credential-name absence without printing the environment.
The request builder independently rejects unexpected fields and never creates
an authorization header. A user-visible failure is a fixed message rather
than an upstream exception or response body.

## Why existing host controls are not the whole answer

SELinux, firewalld, rootless Podman, and systemd are valuable parts of the
host baseline. OpenShell does not replace them; it adds an application-specific
contract at the agent boundary.

| Existing control | What it does well | What OpenShell adds here |
|---|---|---|
| Rootless Podman | isolates a non-root OCI workload | declared file reach, empty capabilities, `NoNewPrivs`, and namespace denial |
| SELinux | enforces host-wide mandatory access policy | workload policy expressed beside the lab and checked as effective at runtime |
| firewalld/security groups | filter addresses, ports, and host exposure | per-sandbox default-deny egress plus auditable process/destination decisions |
| systemd | supervises durable host processes | a durable loopback forward tied to a named OpenShell sandbox service |
| application configuration | selects endpoints and credentials | provider ownership outside application configuration and state |

The layers compose. The CPU host remains guarded by its AWS security group,
RHEL controls, rootless Podman, and a loopback bind. OpenShell then constrains
the application within that host.

## Five progressive workshop labs

The workshop builds evidence one boundary at a time:

1. **Lab 1:** establishes managed GPT-5.5 inference and read-only GitHub API
   access for the designated report tool.
2. **Lab 2:** confines persistent report writes to the reviewed web root while
   retaining bounded scratch paths.
3. **Lab 3:** begins with no ordinary egress, proves the denial, then hot-loads
   the GitHub-only policy and completes the same report workflow.
4. **Lab 4:** moves managed inference to local Qwen on a validated homogeneous
   GPU topology while the application still calls `inference.local`.
5. **Lab 5:** runs a containerized Streamlit UI on the CPU host with no
   ordinary egress and with GPT-5.5 available only through the OpenShell proxy.

Together they show policy iteration, not just a static configuration. An
operator can prove what is denied, add only the needed capability, and preserve
the same application-facing inference contract.

## Run the Lab 5 proof

On the CPU host:

```bash
cd ~/git/openshell-lab
./labs/lab5/build.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
```

From the local workstation, use the gitignored connection state and tunnel the
remote loopback listener:

```bash
source state/cpu-connection.env
ssh -N -L 8501:127.0.0.1:18501 \
  -i "$SSH_KEY_PATH" \
  -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$PWD/state/known_hosts" \
  "$SSH_USER@$PUBLIC_IP"
```

Open `http://127.0.0.1:8501`. The UI explains the Filesystem, Network,
Process, and Provider layers beside the chat. The full operator procedure and
cleanup commands are in [the Lab 5 runbook](../labs/lab5/README.md).

## What production reviewers should ask

- Does a successful model call prove that the application has no ambient
  provider credential? Lab 5 tests both conditions separately.
- Does a connection failure prove policy enforcement? Lab 5 requires a
  corresponding OpenShell denial event.
- Is a non-root UID the complete process boundary? Lab 5 also checks
  capabilities, `NoNewPrivs`, and namespace creation.
- Is the UI reachable from an unintended network? The service forward binds
  only host loopback and requires the documented SSH tunnel.
- Can a policy silently degrade? Landlock is a hard requirement and the
  verifier checks the effective policy, not only the YAML source.

That evidence is the practical value of OpenShell: the operator can state a
small application contract and demonstrate both the intended success path and
the denied alternatives.
