# Lab 5: protected Streamlit managed inference

Lab 5 runs a containerized Streamlit chat application inside the
`openshell-lab5` sandbox on the CPU workshop host. The application calls only
`https://inference.local/v1/chat/completions`; OpenShell selects the existing
`openai-gpt55` provider and supplies GPT-5.5 access outside the application.

The browser path is private by construction:

```text
browser :8501 -> SSH tunnel -> CPU host 127.0.0.1:18501
              -> OpenShell service forward -> sandbox 127.0.0.1:8501
              -> inference.local -> OpenShell-managed provider
```

## Prerequisites

- Complete the CPU deployment for Labs 1–3 so the guarded RHEL host has
  OpenShell, rootless Podman, and the `openai-gpt55` managed-inference route.
- Keep the CPU connection state in the gitignored `state/cpu-connection.env`.
- Run commands on the CPU host from `~/git/openshell-lab`.

Confirm the route without displaying provider state:

```bash
openshell inference get
```

The selected route should identify `openai-gpt55`. The Streamlit image does
not need or receive the provider credential, provider hostname, or model name.

## Build, run, and verify

On the CPU host:

```bash
cd ~/git/openshell-lab
./labs/lab5/build.sh
./labs/lab5/run.sh
./labs/lab5/verify.sh
```

`build.sh` creates a commit-addressed image and records its identity in the
gitignored, owner-only `state/lab5-image.env`. `run.sh` creates the sandbox,
starts Streamlit, and delegates the loopback forward to
`openshell-lab5-forward.service`. `verify.sh` calls the model and tests all four
control layers:

- **Filesystem:** `/opt/openshell-lab` is read-only; only `/tmp` and
  `/dev/null` are writable runtime paths.
- **Network:** ordinary egress has no allow rule, while managed
  `inference.local` traffic uses OpenShell's separate inference route.
- **Process:** the workload runs as `1500:1500`, has an empty capability
  bounding set, has `NoNewPrivs=1`, and cannot create a user/network namespace.
- **Provider:** the application sends no credential or model selection;
  OpenShell owns both.

A successful run leaves the sandbox and forward active for inspection. The
host-only readiness check is:

```bash
curl --silent --show-error --fail \
  http://127.0.0.1:18501/_stcore/health
```

## Open the UI through SSH

From the repository on your local machine:

```bash
source state/cpu-connection.env
ssh -N -L 8501:127.0.0.1:18501 \
  -i "$SSH_KEY_PATH" \
  -o StrictHostKeyChecking=yes \
  -o "UserKnownHostsFile=$PWD/state/known_hosts" \
  "$SSH_USER@$PUBLIC_IP"
```

While that command is running, open `http://127.0.0.1:8501`. The remote
forward stays bound to CPU-host loopback; no Streamlit listener is opened on a
public host interface.

## Expected verification results

The verifier demonstrates both the allowed model path and denied ambient
capabilities:

- `probe.py` returns non-empty assistant text through `inference.local`.
- writing `/opt/openshell-lab/lab5-write-denied` fails;
- a Python request to `https://example.com` fails and has a matching OpenShell
  denial event;
- `CapBnd` is zero, `NoNewPrivs` is one, and `unshare -Urn true` fails;
- the workload contains none of the forbidden provider credential variable
  names checked by the verifier.

Sanitized artifacts are written beneath `evidence/cpu/lab5/`:

```text
health.txt
image-identity.txt
network-denial.log
policy.json
probe.json
process-status.txt
sandbox-create.log
```

Useful read-only inspection commands are:

```bash
systemctl --user status openshell-lab5-forward.service
openshell sandbox get openshell-lab5
openshell policy get openshell-lab5 --full --output json
openshell logs openshell-lab5 --source sandbox -n 300
```

## Cleanup

Stop only Lab 5's forward and sandbox:

```bash
systemctl --user stop openshell-lab5-forward.service
openshell sandbox delete openshell-lab5
```

This does not remove the shared managed provider or alter Labs 1–4.
