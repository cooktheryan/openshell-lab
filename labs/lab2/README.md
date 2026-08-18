# Lab 2: webroot-only filesystem access

This lab keeps Lab 1's GitHub-only network rule and activates Landlock as a
hard requirement. The agent can read its runtime and application files but can
write only beneath `/var/www/html` inside the sandbox.

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

The verifier proves that writes to `/sandbox` and `/tmp` fail while a write to
the webroot succeeds. The host directory persists after sandbox deletion.
