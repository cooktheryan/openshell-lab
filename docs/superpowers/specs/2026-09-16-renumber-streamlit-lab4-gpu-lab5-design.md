# Renumber Streamlit as Lab 4 and GPU Qwen as Lab 5

Date: 2026-09-16
Status: Approved design

## Objective

Reorder the workshop so Labs 1 through 4 run progressively on the same CPU
virtual machine and the capacity-sensitive, higher-cost GPU exercise is the
optional final Lab 5.

The current Streamlit Lab 5 becomes Lab 4. The current Qwen/vLLM GPU Lab 4
becomes Lab 5. This is a clean semantic swap: active paths, runtime identities,
documentation, tests, and evidence use only the new numbering.

## Workshop progression

The resulting sequence is:

1. Lab 1: managed inference with GitHub-only egress.
2. Lab 2: persistent-write confinement.
3. Lab 3: deny-then-allow policy iteration.
4. Lab 4: containerized Streamlit using the same CPU host and managed GPT-5.5
   inference route as Labs 1 through 3.
5. Lab 5: local Qwen inference through vLLM on the guarded GPU host.

The CPU deployment runs Labs 1 through 4. Lab 5 is excluded from that sequence
and is started only through the GPU workflow.

## Clean renumbering

The implementation moves the existing lab directories through a temporary
name so their contents are exchanged without loss:

- the current `labs/lab5` Streamlit application becomes `labs/lab4`;
- the current `labs/lab4` GPU application becomes `labs/lab5`;
- `policies/lab5-streamlit.yaml` becomes `policies/lab4-streamlit.yaml`;
- `src/openshell_lab/lab5_policy.py` becomes
  `src/openshell_lab/lab4_policy.py`;
- Streamlit-specific test and support names move from Lab 5 to Lab 4;
- GPU-specific test, feature, and documentation references move from Lab 4 to
  Lab 5.

There are no compatibility aliases. A lab number has exactly one meaning after
the migration.

## Runtime identities

Streamlit uses the following Lab 4 identities:

- sandbox: `openshell-lab4`;
- image: `localhost/openshell-lab-streamlit:<commit>`;
- image state: `state/lab4-image.env`;
- policy: `policies/lab4-streamlit.yaml`;
- user forward unit: `openshell-lab4-forward.service`;
- sandbox port: `8501`;
- CPU-host loopback port: `18401`;
- evidence: `evidence/cpu/lab4/`.

GPU Qwen uses the following Lab 5 identities:

- sandbox: `openshell-lab5`;
- image: `localhost/openshell-lab-agent:lab5`;
- vLLM and inference route behavior remain otherwise unchanged;
- report forward remains on GPU-host loopback port `18080`;
- evidence remains under `evidence/gpu/`, but all policy and documentation
  descriptions identify it as Lab 5.

The Streamlit application continues to call only
`https://inference.local/v1/chat/completions`. It sends no provider credential,
provider hostname, or model-selection field.

## Orchestration

`infra/remote/run-cpu-labs.sh` runs the Lab 4 Streamlit build, run, and verify
steps immediately after Lab 3 verification. It does not reference Lab 5.

The generated home-directory runner accepts all five explicit lab names. Its
automatic selection remains Lab 3 on a normal CPU host and changes from Lab 4
to Lab 5 when `vllm.service` is active.

The GPU lifecycle scripts continue to guard the exact saved `g6.12xlarge`
instance, AMI, tags, key name, and security group. Renumbering does not broaden
the allowed GPU resource identity or authorize a replacement instance.

## Existing-host migration

The regular lab launchers own only their new sandbox identities. They do not
silently delete the other lab number, because that would make each lab capable
of destroying another lab's runtime.

The runbooks provide explicit one-time cleanup commands:

- on the CPU host, stop `openshell-lab5-forward.service` and delete the old
  `openshell-lab5` Streamlit sandbox before starting the new Lab 4;
- on the GPU host, stop the old Lab 4 forward and delete the old
  `openshell-lab4` sandbox before starting the new Lab 5.

The acceptance run performs these scoped cleanup actions after confirming the
host and sandbox names.

## Documentation

The root README presents Labs 1 through 4 as the CPU path and Lab 5 as the
optional GPU path. It explains that Lab 5 is more expensive and capacity may be
unavailable.

The two lab runbooks, troubleshooting guidance, evidence index,
`openshell-why-it-matters` narrative, commands, sandbox inspection examples,
and diagram labels are updated to the new numbering.

Dated implementation plans remain historical records. Where a historical plan
would otherwise appear current, it receives a short supersession note pointing
to this design instead of having its historical decisions rewritten.

## Evidence policy

The old-numbered checked-in CPU and GPU acceptance evidence is removed rather
than archived.

Fresh CPU acceptance writes the complete Streamlit evidence set to
`evidence/cpu/lab4/`. The collector validates the exact artifact set, rejects
unsafe archive members, redacts each text file, and replaces the local Lab 4
directory without retaining stale files.

Fresh GPU acceptance replaces `evidence/gpu/` only if the guarded GPU instance
starts and the new Lab 5 verification succeeds. If EC2 reports insufficient
capacity, the repository records no current GPU acceptance evidence and the
evidence index states that Lab 5 remote validation is pending capacity.

## EARS and test strategy

Behavior changes are specified before implementation:

- the CPU sequence shall end with the Lab 4 lifecycle;
- the CPU sequence shall not invoke Lab 5;
- an active vLLM service shall make the generated runner default to Lab 5;
- the Streamlit application and verifier shall use Lab 4 identities and port
  `18401`;
- the GPU workflow shall use Lab 5 identities;
- evidence collection shall accept only a complete current Lab 4 set;
- public documentation shall describe Labs 1 through 4 as CPU labs and Lab 5
  as the optional GPU lab.

Each scenario is run red before implementation. Step definitions remain one
per file and delegate to the existing support layer.

Unit and integration coverage is renamed and expanded to check:

- directory and policy mappings;
- CPU orchestration order;
- generated-runner default selection;
- Streamlit image, sandbox, forward, verification, and evidence identities;
- GPU sandbox and image identities;
- absence of stale active Lab 4/5 wording and paths in public documentation;
- credential-free managed inference;
- fail-closed verifier and evidence behavior.

The complete local acceptance command remains `./scripts/verify-all.sh`, which
includes unit tests, Gherkin scenarios, the EARS audit, shell syntax,
ShellCheck when installed, YAML parsing, diagram validation, secret scanning,
and `git diff --check`.

## Remote acceptance

After local verification:

1. Start the guarded CPU instance.
2. Synchronize the repository using the existing secret and large-artifact
   exclusions.
3. Run and verify Labs 1 through 4 sequentially.
4. Confirm Streamlit through the SSH tunnel to CPU-host port `18401`.
5. Collect the new CPU Lab 4 evidence and run the secret scan.
6. Attempt to start the exact guarded GPU `g6.12xlarge` instance.
7. If capacity is available, synchronize the repository, confirm or restore
   vLLM readiness, configure the renamed Lab 5 route, and run and verify Lab 5.
8. Replace GPU evidence only after successful verification.
9. Stop both CPU and GPU instances in cleanup paths, including when a later
   acceptance step fails.
10. Query AWS after each stop and require the `stopped` state.

An `InsufficientInstanceCapacity` response is a valid reported acceptance
constraint, not permission to launch a different GPU host or instance type.

## Completion criteria

The change is complete when:

- all active repository references consistently identify Streamlit as Lab 4
  and GPU Qwen as Lab 5;
- local verification and the secret scan pass;
- CPU Labs 1 through 4 pass remotely and current Lab 4 evidence is collected;
- the guarded GPU start is attempted and Lab 5 passes remotely when capacity is
  available, or the capacity failure is reported accurately;
- both cloud instances are stopped and their stopped states are verified;
- an independent review reports no unresolved critical or important issues;
- all changes and acceptance evidence are committed locally.
