# Lab 1: GitHub-only network access

This lab runs the merge-report agent through OpenShell with no filesystem
restriction. Its enforced network policy permits only read-only HTTPS requests
to `api.github.com`, and only when `/usr/bin/curl` makes the request.

On the RHEL host, configure the model route once and run the lab:

```shell
export OPENAI_API_KEY='enter the key in your shell'
./labs/lab1/configure-openai.sh
./labs/lab1/run.sh
./labs/lab1/verify.sh
```

The setup command sends the key to the local OpenShell gateway through a bare
environment lookup, then unsets it. The sandbox receives neither the real key
nor a model name; it calls `https://inference.local/v1/chat/completions`.

The generated report is downloaded to
`evidence/lab1/nvidia-openshell-last-5-merges.md`.
