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
