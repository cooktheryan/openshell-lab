from behave import when
from behave.api.pending_step import StepNotImplementedError


@when('the report agent writes beneath "{path}"')
def step_filesystem_write(context, path):
    raise StepNotImplementedError(f"filesystem action is not implemented: {path}")
