@report
Feature: Evidence-grounded merge reporting
  The lab reports the latest NVIDIA/OpenShell merge activity without inventing relationships.

  @event-driven
  Rule: When report generation is requested, the report agent shall select exactly five distinct merged pull requests in descending merge-time order.

    Scenario: Closed pull requests are filtered to the latest five merges
      Given merge evidence is "mixed merged and unmerged pull requests"
      When the "recent merge selection" operation is performed
      Then the selected evidence should contain five unique merged pull requests
      And the selected evidence should be ordered from newest to oldest

  @event-driven
  Rule: When a selected pull request references an issue, the evidence collector shall record only explicit issue relationships.

    Scenario: Explicit issue references are retained
      Given merge evidence is "explicit and implicit issue candidates"
      When the "issue relationship identification" operation is performed
      Then only explicitly referenced issues should be associated

  @event-driven
  Rule: When the model publishes a report, the report agent shall validate the required Markdown evidence for all five selected pull requests.

    Scenario: A complete evidence-grounded report is accepted
      Given the report fixture is "complete"
      When the report agent validates the Markdown
      Then the report validation should be "accepted"

    Scenario: A report with a missing pull request is rejected
      Given the report fixture is "missing one pull request"
      When the report agent validates the Markdown
      Then the report validation should be "rejected"

  @security
  @unwanted-behavior
  Rule: If report content contains credential material, then the report agent shall reject publication.

    Scenario: Credential-bearing Markdown is rejected
      Given the report fixture is "credential-bearing"
      When the report agent validates the Markdown
      Then the report validation should be "rejected"
