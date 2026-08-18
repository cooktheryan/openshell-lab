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

  @state-driven
  Rule: While Lab 4 is active, the GPU deployment shall serve Qwen3.6-27B through four L40S GPUs with a 32768-token context limit.

    Scenario: GPU inference settings match the validated topology
      Given the "GPU deployment" configuration is available
      When the "GPU inference configuration" is evaluated
      Then the deployment should use the validated Qwen topology
