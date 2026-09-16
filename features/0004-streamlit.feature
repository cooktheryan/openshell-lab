@streamlit
@security
Feature: Streamlit managed inference
  Lab 4 serves a bounded chat UI through OpenShell without application credentials.

  @ubiquitous
  Rule: The Lab 4 Streamlit application shall send model requests through inference.local without provider credentials or model selection.

    Scenario: Streamlit request uses the managed inference route
      Given the "Lab 4 managed inference" configuration is available
      When the "Streamlit model request" is evaluated
      Then the Streamlit request should use managed inference

  @unwanted-behavior
  Rule: If a Lab 4 prompt is empty or exceeds 4000 characters, then the Streamlit inference client shall reject it before model access.

    Scenario Outline: Invalid Streamlit input is rejected
      Given the Streamlit prompt is "<prompt_state>"
      When the "Streamlit input validation" is evaluated
      Then the Streamlit input should be rejected

      Examples: Invalid prompt boundaries
        | prompt_state         |
        | empty                |
        | over 4000 characters |

  @ubiquitous
  Rule: The Lab 4 application image shall run Streamlit with the numeric non-root identity 1500:1500.

    Scenario: Streamlit image declares the approved identity
      Given the "Streamlit image metadata" configuration is available
      When the "image identity" is evaluated
      Then the image identity should be non-root

  @state-driven
  Rule: While Lab 4 is active, the OpenShell filesystem policy shall expose application code as read-only and confine runtime writes to /tmp and /dev/null.

    Scenario: Streamlit runtime state is writable
      Given the "Lab 4" policy is loaded
      When the report agent writes beneath "/tmp"
      Then the filesystem action should be "allowed"

    Scenario: Streamlit application code is not writable
      Given the "Lab 4" policy is loaded
      When the report agent writes beneath "/opt/openshell-lab/app.py"
      Then the filesystem action should be "denied"

  @state-driven
  Rule: While Lab 4 is active, the OpenShell network policy shall deny all ordinary egress.

    Scenario: Lab 4 ordinary egress is absent
      Given the "Lab 4" policy is loaded
      When the "Lab 4 network posture" is evaluated
      Then the Lab 4 ordinary network policy should be empty

  @security
  @state-driven
  Rule: While Lab 4 is available to a browser, the Streamlit forward shall maintain a durable loopback-only mapping from host port 18401 to sandbox port 8501.

    Scenario: Streamlit uses a durable loopback-only forward
      Given the "Lab 4 launcher" configuration is available
      When the "Lab 4 forward configuration" is evaluated
      Then the Lab 4 forward should be loopback only

  @unwanted-behavior
  Rule: If a Lab 4 security probe fails for an operational reason or the live forward is not loopback-only, then verification shall fail without accepting that condition as confinement evidence.

    Scenario: Operational probe failure is rejected
      Given the "Lab 4 verifier" configuration is available
      When the "verifier denial controls" is evaluated
      Then expected denials should be distinguished from operational failures

    Scenario: A publicly bound live forward is rejected
      Given the "Lab 4 verifier" configuration is available
      When the "live listener controls" is evaluated
      Then verification should require a live loopback listener

  @event-driven
  Rule: When a Lab 4 chat message is appended, the application shall retain no more than the newest 20 conversation messages even if managed inference fails.

    Scenario: Failed inference retains bounded history
      Given the "Lab 4 managed inference" configuration is available
      When the "Streamlit failed inference history" is evaluated
      Then the Streamlit conversation history should remain bounded

  @event-driven
  Rule: When Lab 4 evidence is collected, the collector shall require one complete current artifact set and replace the prior local set without retaining stale files.

    Scenario: Lab 4 evidence replacement is complete
      Given the "Lab 4 evidence collector" configuration is available
      When the "evidence integrity controls" is evaluated
      Then collection should reject partial or mixed evidence
