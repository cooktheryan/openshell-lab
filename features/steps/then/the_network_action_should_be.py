from behave import then
from features.steps.support.lab_checks import LabChecks


@then('the network action should be "{status}"')
def step_network_status(context, status):
    LabChecks(context).assert_network_action(status)
