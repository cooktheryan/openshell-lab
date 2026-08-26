# Lab 2: webroot-only filesystem access

This lab keeps Lab 1's GitHub-only network rule and activates Landlock as a
hard requirement. The agent can read its runtime and application files but can
persist output only beneath `/var/www/html` inside the sandbox. OpenShell's
required runtime baseline also permits `/tmp` scratch data and `/dev/null`.

The application is built into a numeric non-root image before sandbox
creation. This is necessary because OpenShell correctly prevents a later SSH
upload from writing into the policy's read-only application path.

The Podman driver bind-mounts the host directory
`/var/www/html/openshell-lab` at the sandbox path `/var/www/html`. Because RHEL
SELinux labels that bind for the container, Apache publishes it through a
loopback-only static server forwarded by OpenShell.

Run on the RHEL host:

```shell
./labs/lab2/configure-host.sh
./labs/lab2/run.sh
./labs/lab2/verify.sh
```

The report is available at:

```text
http://HOST_PUBLIC_IP/openshell-lab/nvidia-openshell-last-5-merges.md
```

The verifier proves that writes to `/sandbox` fail while webroot publication
and temporary runtime scratch succeed. Only the host webroot persists after
sandbox deletion.

Sandbox-creation diagnostics are retained in
`evidence/lab2/sandbox-create.log`. Stop this lab's loopback forward before a
later lab reuses port 18080:

```shell
openshell forward stop 18080 openshell-lab2
```
