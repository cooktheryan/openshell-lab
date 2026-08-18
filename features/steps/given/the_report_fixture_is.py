from behave import given
from behave.api.pending_step import StepNotImplementedError


@given('the report fixture is "{state}"')
def step_report_fixture(context, state):
    raise StepNotImplementedError(f"report fixture is not implemented: {state}")
