@deployment
Feature: AWS lab deployment
  The deployment uses reviewed AWS resources and protects operator credentials.

  @ubiquitous
  Rule: The CPU lab launcher shall request the approved RHEL 10 t3.micro configuration in us-east-1.

    Scenario: CPU launch settings match the approved design
      Given the "CPU launch" configuration is available
      When the "CPU launch configuration" is evaluated
      Then the launch should use the approved CPU settings

  @security
  @event-driven
  Rule: When a CPU launch is requested, the launcher shall serialize local launches and persist the new instance identity before health waits.

    Scenario: CPU launch failure retains a recoverable instance identity
      Given the "CPU launch" configuration is available
      When the "CPU launch safety" is evaluated
      Then the launcher should serialize launches and persist provisional state

  @security
  @unwanted-behavior
  Rule: If the saved CPU instance is not t3.micro, then the CPU lifecycle shall reject the start without requesting an instance mutation.

    Scenario: Resized CPU instance is rejected before start
      Given a saved CPU instance with valid project tags and type "m5.large"
      When the operator requests a CPU start
      Then the CPU start should fail without requesting an instance mutation

  @security
  @ubiquitous
  Rule: The lab repository shall exclude credential and private-key material from version control.

    Scenario Outline: Sensitive artifacts are excluded
      Given a candidate repository artifact of type "<artifact>"
      When the "repository safety" is evaluated
      Then the artifact should be excluded

      Examples: Credential-bearing artifacts
        | artifact            |
        | environment file    |
        | SSH private key     |
        | OpenShell database  |
        | TLS private key     |
        | model cache         |

  @security
  @event-driven
  Rule: When the RHEL bootstrap installs OpenShell, the bootstrap shall select and verify the current stable NVIDIA release.

    Scenario: OpenShell installation follows the latest stable release
      Given the "OpenShell release installation" configuration is available
      When the "OpenShell release selection" is evaluated
      Then the bootstrap should resolve and verify the latest stable release

  @reliability
  @state-driven
  Rule: While an OpenShell lab sandbox is active, each lab launcher shall keep its canonical process running.

    Scenario: Lab sandboxes retain a durable canonical process
      Given the "sandbox launchers" configuration is available
      When the "canonical sandbox process configuration" is evaluated
      Then every lab launcher should use a durable canonical process

  @reliability
  @event-driven
  Rule: When Lab 1 stages agent source for a sandbox with a canonical process, the Lab 1 launcher shall upload the source after sandbox creation and before agent execution.

    Scenario: Lab 1 stages source without conflicting create options
      Given the "Lab 1 launcher" configuration is available
      When the "source upload ordering" is evaluated
      Then the source upload should follow creation and precede agent execution

  @reliability
  @event-driven
  Rule: When Lab 5 prepares its loopback forward, the Lab 5 launcher shall stop only the active sandbox forward.

    Scenario: Lab 5 cleans up its own loopback forward
      Given the "Lab 5 launcher" configuration is available
      When the "loopback forward cleanup" is evaluated
      Then the forward cleanup should target the active sandbox

  @reliability
  @state-driven
  Rule: While a loopback forward remains active, each forwarded lab launcher shall allow its invoking non-interactive session to complete.

    Scenario: Forwarded launchers release the invoking session
      Given the "forwarded sandbox launchers" configuration is available
      When the "non-interactive forward lifecycle" is evaluated
      Then each invoking session should complete while its forward remains active

  @reliability
  @state-driven
  Rule: While the Lab 3 deny policy is active, the Lab 3 launcher shall use a bounded GitHub probe and confirm that no report exists before loading the allow policy and executing the report agent once.

    Scenario: Lab 3 safely transitions from denied to allowed GitHub access
      Given the "Lab 3 launcher" configuration is available
      When the "Lab 3 deny-to-allow transition" is evaluated
      Then the denied GitHub probe should be bounded and precede one report agent execution

  @reliability
  @event-driven
  Rule: When CPU Lab 2 verification completes, the CPU deployment shall stop the Lab 2 forward before starting Lab 3.

    Scenario: Sequential CPU labs do not compete for the report port
      Given the "CPU lab sequence" configuration is available
      When the "CPU forward lifecycle" is evaluated
      Then the Lab 2 forward should stop before Lab 3 starts

  @security
  @unwanted-behavior
  Rule: If ripgrep is unavailable during repository scanning, then the secret scanner shall reject credential-bearing content with an available system search tool.

    Scenario: Scanner rejects a credential without ripgrep
      Given the "secret scanner without ripgrep" configuration is available
      When the "secret scanner fallback" is evaluated
      Then credential-bearing content should be rejected without exposing it

  @security
  @unwanted-behavior
  Rule: If a repository search tool reports an execution error, then the secret scanner shall fail the scan without reporting clean.

    Scenario: Search tool failure cannot produce a clean result
      Given the "failing secret search tool" configuration is available
      When the "secret search tool failure" is evaluated
      Then the secret scan should fail without reporting clean

  @security
  @unwanted-behavior
  Rule: If repository content contains a temporary AWS identifier or an assigned AWS secret or session value, then the secret scanner shall reject the file through either supported search implementation without emitting the value.

    Scenario: AWS credentials are rejected by both scanner implementations
      Given the "AWS credential scanner matrix" configuration is available
      When the "AWS credential scanner matrix" is evaluated
      Then AWS credential forms should be rejected by both scanner implementations without exposure

  @state-driven
  Rule: While Lab 5 is active, the GPU deployment configuration shall run Qwen3.6-27B through exactly four homogeneous L4 or L40S GPUs with a 32768-token context limit.

    Scenario: GPU inference settings match the validated topology
      Given the "GPU deployment" configuration is available
      When the "GPU inference configuration" is evaluated
      Then the deployment configuration should declare the validated Qwen topology

  @state-driven
  Rule: While Lab 5 uses four homogeneous L4 or L40S GPUs, the GPU profile selector shall configure 16 maximum concurrent sequences for L4 or 256 for L40S.

    Scenario Outline: GPU concurrency matches the supported topology
      Given the GPU topology is "<topology>"
      When the "GPU profile selection" is evaluated
      Then the maximum concurrent sequence limit should be "<maximum_sequences>"

      Examples:
        | topology              | maximum_sequences |
        | four NVIDIA L4 GPUs   | 16                |
        | four NVIDIA L40S GPUs | 256               |

  @unwanted-behavior
  Rule: If Lab 5 detects a mixed, unsupported, or non-four-GPU topology, then the GPU profile selector shall reject the configuration.

    Scenario Outline: Unsupported GPU topology is rejected
      Given the GPU topology is "<topology>"
      When the "GPU profile selection" is evaluated
      Then the GPU profile selection should be rejected

      Examples:
        | topology                  |
        | three NVIDIA L4 GPUs      |
        | mixed NVIDIA GPUs         |
        | four NVIDIA RTX PRO GPUs  |

  @reliability
  @event-driven
  Rule: When Lab 3 verification completes, the CPU deployment shall execute the Lab 4 Streamlit lifecycle on its distinct port 18401.

    Scenario: Lab 4 follows the report labs on a distinct forward
      Given the "CPU lab sequence" configuration is available
      When the "CPU Lab 4 sequence" is evaluated
      Then Lab 4 should follow Lab 3 without invoking Lab 5

  @state-driven
  Rule: While vLLM is active, the generated home runner shall select Lab 5 as its default lab.

    Scenario: GPU host defaults to Lab 5
      Given the "home runner installer" configuration is available
      When the "GPU default lab" is evaluated
      Then the generated runner should default to Lab 5

  @reliability
  @event-driven
  Rule: When an evidence archive is received, the CPU and GPU evidence collectors shall require exactly one occurrence of each artifact before extraction.

    Scenario Outline: Exact archive member occurrences are accepted
      Given the "<collector> evidence collector" configuration is available
      When the "single archive member occurrences" is evaluated
      Then the collector should publish the exact artifact set

      Examples: Evidence collectors
        | collector |
        | CPU       |
        | GPU       |

    Scenario Outline: Duplicate archive member occurrences are rejected
      Given the "<collector> evidence collector" configuration is available
      When the "duplicate archive member occurrences" is evaluated
      Then the collector should reject duplicate archive members without replacing prior evidence

      Examples: Evidence collectors
        | collector |
        | CPU       |
        | GPU       |

  @reliability
  @unwanted-behavior
  Rule: If the configured remote repository directory cannot be selected, then the CPU and GPU evidence collectors shall abort transfer before replacing the prior published set.

    Scenario Outline: Failed remote directory selection preserves evidence
      Given the "<collector> evidence collector" configuration is available
      When the "failed remote evidence directory selection" is evaluated
      Then the collector should preserve prior evidence after remote directory selection fails

      Examples: Evidence collectors
        | collector |
        | CPU       |
        | GPU       |

  @documentation
  @ubiquitous
  Rule: The Lab 5 runbook shall identify the optional Qwen GPU lifecycle and its capacity-pending acceptance status.

    Scenario: Lab 5 guidance has one unambiguous identity
      Given the "public Lab 5 documentation" configuration is available
      When the "Lab 5 runbook identity" is evaluated
      Then the Lab 5 runbook should describe the GPU lifecycle and pending acceptance

  @documentation
  @ubiquitous
  Rule: The acceptance evidence index shall distinguish the current gitignored connection address from the acceptance-time CPU address snapshot.

    Scenario: Current and acceptance-time CPU addresses have distinct records
      Given the "public Lab 5 documentation" configuration is available
      When the "CPU address evidence semantics" is evaluated
      Then the evidence index should distinguish current connection state from the acceptance snapshot

  @documentation
  @state-driven
  Rule: While Lab 5 GPU acceptance is pending capacity, the acceptance evidence index shall classify the GPU artifact paths as expected rather than current.

    Scenario: Pending GPU artifacts are not presented as current evidence
      Given the "public Lab 5 documentation" configuration is available
      When the "pending GPU evidence semantics" is evaluated
      Then the evidence index should classify absent GPU artifacts as pending capacity
