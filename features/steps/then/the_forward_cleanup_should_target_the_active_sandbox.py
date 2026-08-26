from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the forward cleanup should target the active sandbox")
def step_active_sandbox_forward_cleanup(context):
    LabChecks(context).assert_lab4_forward_cleanup()
