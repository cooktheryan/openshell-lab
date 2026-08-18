from behave import then
from behave.api.pending_step import StepNotImplementedError


@then('the filesystem action should be "{status}"')
def step_filesystem_status(context, status):
    raise StepNotImplementedError(f"filesystem assertion is not implemented: {status}")
