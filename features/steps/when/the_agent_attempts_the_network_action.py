from behave import when
from features.steps.support.lab_checks import LabChecks


@when('the agent attempts the network action "{action}"')
def step_network_action(context, action):
    LabChecks(context).evaluate_network_action(action)
