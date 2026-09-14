from behave import then
from features.steps.support.lab_checks import LabChecks


@then("every lab launcher should use a durable canonical process")
def step_durable_canonical_process(context):
    LabChecks(context).assert_durable_canonical_processes()
