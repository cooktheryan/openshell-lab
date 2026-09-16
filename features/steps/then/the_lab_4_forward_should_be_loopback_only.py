from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Lab 4 forward should be loopback only")
def step_lab4_forward_loopback_only(context):
    LabChecks(context).assert_lab4_forward_loopback_only()
