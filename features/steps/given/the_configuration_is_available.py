from behave import given
from behave.api.pending_step import StepNotImplementedError


@given('the "{configuration}" configuration is available')
def step_configuration_available(context, configuration):
    raise StepNotImplementedError(f"configuration fixture is not implemented: {configuration}")
