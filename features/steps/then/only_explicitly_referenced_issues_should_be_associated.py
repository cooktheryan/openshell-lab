from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("only explicitly referenced issues should be associated")
def step_explicit_issues(context):
    raise StepNotImplementedError("issue association assertion is not implemented")
