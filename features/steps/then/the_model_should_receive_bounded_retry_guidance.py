from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the model should receive bounded retry guidance")
def step_bounded_tool_retry(context):
    LabChecks(context).assert_bounded_tool_retry()
