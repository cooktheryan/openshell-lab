# Lab 3: containerized agent with deny then allow

Lab 3 builds the report application into a Podman image derived from the pinned
stable `quay.io/aipcc/agentic-ci/openshell` image. The application declares the
numeric OCI identity `1500:1500`; OpenShell still launches its supervisor as
root and drops the workload to the image identity.

Run on the RHEL host after Lab 2:

```shell
openshell forward stop 18080 openshell-lab2
./labs/lab3/build.sh
./labs/lab3/run.sh
./labs/lab3/verify.sh
```

The CPU sequence runner performs the same handoff automatically:

```shell
./infra/remote/run-cpu-labs.sh
```

The sandbox starts with `lab3-network-deny.yaml`. A bounded direct curl probe
must be rejected, the sandbox audit log must attribute that rejection to the
network policy, and the launcher confirms that no report exists before it
replaces the dynamic network policy with `lab3-github-allow.yaml`. Operational
probe, log, and filesystem-check errors fail closed. After the allow policy
activates, the report agent runs exactly once and must publish the report. Both
policies retain the same hard-required webroot-only filesystem posture, so the
hot update changes no static control.

Policy snapshots, denial audit events, sandbox logs, and sandbox-creation
diagnostics are retained under `evidence/lab3`. Deleting the sandbox does not delete
`/var/www/html/openshell-lab` on the host.
