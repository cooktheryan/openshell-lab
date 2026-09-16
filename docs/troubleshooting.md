# Troubleshooting

## `MainProcessExited: Canonical main process exited`

The command after `--` in `openshell sandbox create` is the sandbox's canonical
process. A short-lived command such as `/bin/true` exits during provisioning and
puts the sandbox into the error phase. Keep it alive while using later
`openshell sandbox exec` calls:

```shell
openshell sandbox create \
  --name example \
  --from localhost/example:latest \
  --policy policy.yaml \
  --no-tty \
  -- /usr/bin/sleep infinity
```

## `pip install openshell` succeeds but no `openshell` command is installed

Starting with v0.0.113, the Python wheel contains the SDK but not the CLI. Use
the release installer (as `infra/remote/bootstrap-rhel10.sh` does) to install
the CLI and gateway service. Confirm the result with `openshell --version`.

## The user gateway service is inactive

The gateway must be running before sandbox creation. Enable it for the current
user, then wait for the CLI health check to connect:

```shell
systemctl --user enable --now openshell-gateway
openshell status
```

## OpenShell reports connection refused after a gateway restart

Wait for `openshell status` to report connected. The bootstrap and Apache
configuration scripts include bounded readiness loops because registration and
the listener become ready asynchronously.

## A sandbox name already exists after deletion

Deletion is asynchronous. The lab scripts wait until `openshell sandbox list
--names` no longer contains the name before recreating it.

## Local inference returns 503

Confirm vLLM locally with `curl http://127.0.0.1:8000/v1/models`, then inspect
`openshell logs SANDBOX --source sandbox`. The provider must use
`host.openshell.internal`, not the EC2 private IP; the injected alias crosses
the isolated sandbox namespace. Gateway-side verification cannot resolve that
alias, so the configuration script performs a local preflight before using
`openshell inference set --no-verify`.

## vLLM has not opened port 8000

The first start can spend several minutes loading weights, compiling kernels,
profiling memory, and capturing CUDA graphs. Follow `podman logs -f
vllm-qwen36`. All four worker processes should appear in `nvidia-smi`.

## Apache returns 403 or 502

Run `sudo apachectl configtest && sudo systemctl reload httpd`. Confirm the
OpenShell forward with `openshell forward list` and fetch port 18080 directly.
SELinux remains enforcing; do not disable it. `httpd_can_network_connect` must
be enabled for the loopback reverse proxy.

## A non-interactive SSH command does not return after a forwarded lab passes

OpenShell v0.0.113 keeps the loopback forward active after `sandbox create`
returns. If that background process inherits SSH standard error, the remote
command can appear to hang because the SSH pipe remains open. The lab launchers
redirect sandbox-creation diagnostics to `evidence/lab2/sandbox-create.log`,
`evidence/lab3/sandbox-create.log`, or `evidence/gpu/sandbox-create.log` so the
invoking session can close independently.

Only one sandbox can own host port 18080 at a time. Before starting Lab 3 after
Lab 2 manually, run:

```shell
openshell forward stop 18080 openshell-lab2
```

`infra/remote/run-cpu-labs.sh` performs this transition automatically and
leaves the Lab 3 forward active for evidence collection.

## A CPU host still has the pre-renumbering Streamlit sandbox

The protected Streamlit exercise is now Lab 4. Before its first run on a CPU
host that previously ran it as Lab 5, perform this one-time cleanup:

```shell
systemctl --user stop openshell-lab5-forward.service
openshell sandbox delete openshell-lab5
```

Then use `./labs/lab4/build.sh`, `./labs/lab4/run.sh`, and
`./labs/lab4/verify.sh`. The current CPU-host forward is
`openshell-lab4-forward.service` on `127.0.0.1:18401`; do not expose it through
the security group.

## A GPU host still has the pre-renumbering Qwen sandbox

The Qwen/vLLM exercise is now optional Lab 5. Before its first run on a GPU
host that previously ran it as Lab 4, perform this one-time cleanup:

```shell
openshell forward stop 18080 openshell-lab4
openshell sandbox delete openshell-lab4
```

Then configure and run `./labs/lab5/`. A guarded GPU start can report
`InsufficientInstanceCapacity`; leave Lab 5 acceptance pending capacity rather
than selecting another host or instance type.

## The secret scan prints `rg: command not found`

The scanner uses ripgrep when installed and otherwise falls back to system
`grep`. If neither command exists, it exits with an error rather than reporting
a false clean result.

## `/tmp` is writable despite a webroot policy

Proxy mode enriches policies with a minimum Landlock runtime baseline. The
labs explicitly record `/tmp` and `/dev/null` as runtime paths. Persistent
output remains limited to the mounted webroot, and `/sandbox`, `/home`, and
`/etc` writes are denied.
