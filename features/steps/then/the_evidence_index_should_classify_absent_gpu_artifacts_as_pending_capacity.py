from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the evidence index should classify absent GPU artifacts as pending capacity")
def step_pending_gpu_evidence_semantics(context):
    LabChecks(context).assert_pending_gpu_evidence_semantics()
