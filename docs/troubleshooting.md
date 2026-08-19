# Troubleshooting

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

## `/tmp` is writable despite a webroot policy

Proxy mode enriches policies with a minimum Landlock runtime baseline. The
labs explicitly record `/tmp` and `/dev/null` as runtime paths. Persistent
output remains limited to the mounted webroot, and `/sandbox`, `/home`, and
`/etc` writes are denied.
