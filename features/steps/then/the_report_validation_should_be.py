from behave import then
from behave.api.pending_step import StepNotImplementedError


@then('the report validation should be "{status}"')
def step_report_status(context, status):
    raise StepNotImplementedError(f"report status assertion is not implemented: {status}")
