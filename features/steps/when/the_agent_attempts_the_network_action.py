from behave import when
from behave.api.pending_step import StepNotImplementedError


@when('the agent attempts the network action "{action}"')
def step_network_action(context, action):
    raise StepNotImplementedError(f"network action is not implemented: {action}")
