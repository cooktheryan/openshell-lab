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
  Rule: When Lab 4 prepares its loopback forward, the Lab 4 launcher shall stop only the active sandbox forward.

    Scenario: Lab 4 cleans up its own loopback forward
      Given the "Lab 4 launcher" configuration is available
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

  @state-driven
  Rule: While Lab 4 is active, the GPU deployment configuration shall declare Qwen3.6-27B through four L40S GPUs with a 32768-token context limit.

    Scenario: GPU inference settings match the validated topology
      Given the "GPU deployment" configuration is available
      When the "GPU inference configuration" is evaluated
      Then the deployment configuration should declare the validated Qwen topology
