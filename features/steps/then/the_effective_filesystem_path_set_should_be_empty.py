from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the effective filesystem path set should be empty")
def step_empty_filesystem_paths(context):
    raise StepNotImplementedError("filesystem policy assertion is not implemented")
