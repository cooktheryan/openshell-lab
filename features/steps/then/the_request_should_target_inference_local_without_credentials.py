from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the request should target inference.local without credentials")
def step_managed_request(context):
    LabChecks(context).assert_managed_request()
