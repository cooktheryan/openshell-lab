from behave import then
from features.steps.support.lab_checks import LabChecks


@then("collection should reject partial or mixed evidence")
def step_lab4_evidence_integrity(context):
    LabChecks(context).assert_lab4_evidence_integrity()
