from behave import when
from behave.api.pending_step import StepNotImplementedError


@when('the "{operation}" operation is performed')
def step_operation(context, operation):
    raise StepNotImplementedError(f"operation is not implemented: {operation}")
