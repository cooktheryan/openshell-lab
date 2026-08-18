# Lab 3: containerized agent with deny then allow

Lab 3 builds the report application into a Podman image derived from the pinned
stable `quay.io/aipcc/agentic-ci/openshell` image. The application declares the
numeric OCI identity `1500:1500`; OpenShell still launches its supervisor as
root and drops the workload to the image identity.

Run on the RHEL host after Lab 2:

```shell
./labs/lab3/build.sh
./labs/lab3/run.sh
./labs/lab3/verify.sh
```

The first run uses `lab3-network-deny.yaml` and must fail before gathering
GitHub evidence. The script then replaces the dynamic network policy with
`lab3-github-allow.yaml`, waits for activation, and reruns the same image. The
second run must publish the report. Both policies retain the same hard-required
webroot-only filesystem posture, so the hot update changes no static control.

Policy snapshots and sandbox logs are retained under `evidence/lab3`. Deleting
the sandbox does not delete `/var/www/html/openshell-lab` on the host.
