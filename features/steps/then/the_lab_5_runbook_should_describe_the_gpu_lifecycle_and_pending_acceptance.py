from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Lab 5 runbook should describe the GPU lifecycle and pending acceptance")
def step_lab5_runbook_identity(context):
    LabChecks(context).assert_lab5_runbook_identity()
