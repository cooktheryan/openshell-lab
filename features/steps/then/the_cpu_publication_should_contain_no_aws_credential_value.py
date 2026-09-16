from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the CPU publication should contain no AWS credential value")
def step_cpu_aws_evidence_redaction(context):
    LabChecks(context).assert_cpu_aws_evidence_redaction()
