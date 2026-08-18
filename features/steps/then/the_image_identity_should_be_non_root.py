from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the image identity should be non-root")
def step_non_root_image(context):
    raise StepNotImplementedError("image identity assertion is not implemented")
