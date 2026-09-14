@streamlit
@security
Feature: Streamlit managed inference
  Lab 5 serves a bounded chat UI through OpenShell without application credentials.

  @ubiquitous
  Rule: The Lab 5 Streamlit application shall send model requests through inference.local without provider credentials or model selection.

    Scenario: Streamlit request uses the managed inference route
      Given the "Lab 5 managed inference" configuration is available
      When the "Streamlit model request" is evaluated
      Then the Streamlit request should use managed inference

  @unwanted-behavior
  Rule: If a Lab 5 prompt is empty or exceeds 4000 characters, then the Streamlit inference client shall reject it before model access.

    Scenario Outline: Invalid Streamlit input is rejected
      Given the Streamlit prompt is "<prompt_state>"
      When the "Streamlit input validation" is evaluated
      Then the Streamlit input should be rejected

      Examples: Invalid prompt boundaries
        | prompt_state         |
        | empty                |
        | over 4000 characters |

  @ubiquitous
  Rule: The Lab 5 application image shall run Streamlit with the numeric non-root identity 1500:1500.

    Scenario: Streamlit image declares the approved identity
      Given the "Streamlit image metadata" configuration is available
      When the "image identity" is evaluated
      Then the image identity should be non-root

  @state-driven
  Rule: While Lab 5 is active, the OpenShell filesystem policy shall expose application code as read-only and confine runtime writes to /tmp and /dev/null.

    Scenario: Streamlit runtime state is writable
      Given the "Lab 5" policy is loaded
      When the report agent writes beneath "/tmp"
      Then the filesystem action should be "allowed"

    Scenario: Streamlit application code is not writable
      Given the "Lab 5" policy is loaded
      When the report agent writes beneath "/opt/openshell-lab/app.py"
      Then the filesystem action should be "denied"

  @state-driven
  Rule: While Lab 5 is active, the OpenShell network policy shall deny all ordinary egress.

    Scenario: Lab 5 ordinary egress is absent
      Given the "Lab 5" policy is loaded
      When the "Lab 5 network posture" is evaluated
      Then the Lab 5 ordinary network policy should be empty
