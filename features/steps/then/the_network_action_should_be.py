from behave import then
from behave.api.pending_step import StepNotImplementedError


@then('the network action should be "{status}"')
def step_network_status(context, status):
    raise StepNotImplementedError(f"network assertion is not implemented: {status}")
