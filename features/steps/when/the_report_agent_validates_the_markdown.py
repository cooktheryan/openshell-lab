from behave import when
from behave.api.pending_step import StepNotImplementedError


@when("the report agent validates the Markdown")
def step_validate_markdown(context):
    raise StepNotImplementedError("Markdown validation is not implemented")
