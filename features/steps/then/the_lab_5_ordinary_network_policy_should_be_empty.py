from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Lab 5 ordinary network policy should be empty")
def step_lab5_network_policy_empty(context):
    LabChecks(context).assert_lab5_network_policy_empty()
