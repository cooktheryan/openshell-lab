@security
Feature: OpenShell agent controls
  Each lab demonstrates an explicit network and filesystem security posture.

  @state-driven
  Rule: While Lab 1 is active, the OpenShell sandbox shall retain its baseline writable workdir and temporary-directory posture.

    Scenario: Lab 1 uses the OpenShell baseline filesystem posture
      Given the "Lab 1" policy is loaded
      When the "filesystem posture" is evaluated
      Then the filesystem posture should include the workdir and temporary directory

  @state-driven
  Rule: While the report agent uses ordinary egress, OpenShell shall allow only read-only GitHub API access by the designated curl binary.

    Scenario: The designated curl binary reads GitHub
      Given the "GitHub-only network" policy is loaded
      When the designated curl binary reads the GitHub API
      Then the network action should be "allowed"

    Scenario Outline: Undeclared egress is denied
      Given the "GitHub-only network" policy is loaded
      When the agent attempts the network action "<action>"
      Then the network action should be "denied"

      Examples: Requests outside the declared binary and endpoint scope
        | action                   |
        | read a different host    |
        | read GitHub with Python  |
        | mutate the GitHub API    |

  @state-driven
  Rule: While filesystem confinement is active, OpenShell shall allow persistent agent writes only beneath /var/www/html and retain bounded runtime scratch paths.

    Scenario: The report is written to the publication directory
      Given the "webroot-only filesystem" policy is loaded
      When the report agent writes beneath "/var/www/html"
      Then the filesystem action should be "allowed"

    Scenario: Temporary runtime state is writable
      Given the "webroot-only filesystem" policy is loaded
      When the report agent writes beneath "/tmp"
      Then the filesystem action should be "allowed"

    Scenario Outline: A non-publication write is denied
      Given the "webroot-only filesystem" policy is loaded
      When the report agent writes beneath "<path>"
      Then the filesystem action should be "denied"

      Examples: Paths outside the publication directory
        | path     |
        | /sandbox |
        | /home    |
        | /etc     |
        | /tmp/../etc |
        | /dev/null/child |

  @ubiquitous
  Rule: The containerized report agent shall run with a non-root OCI identity.

    Scenario: The application image declares a numeric unprivileged user
      Given the "application image metadata" configuration is available
      When the "image identity" is evaluated
      Then the image identity should be non-root

  @security
  @ubiquitous
  Rule: The report agent shall use managed inference without receiving provider credentials.

    Scenario: The model request contains no provider secret
      Given the "managed inference route" configuration is available
      When the "model request" is evaluated
      Then the request should target inference.local without credentials
