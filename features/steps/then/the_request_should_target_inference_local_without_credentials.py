from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the request should target inference.local without credentials")
def step_managed_request(context):
    raise StepNotImplementedError("managed inference assertion is not implemented")
