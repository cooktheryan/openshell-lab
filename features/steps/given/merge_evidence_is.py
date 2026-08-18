from behave import given
from behave.api.pending_step import StepNotImplementedError


@given('merge evidence is "{state}"')
def step_merge_evidence(context, state):
    raise StepNotImplementedError(f"merge evidence fixture is not implemented: {state}")
