from behave import given
from behave.api.pending_step import StepNotImplementedError


@given('the "{policy_name}" policy is loaded')
def step_policy_loaded(context, policy_name):
    raise StepNotImplementedError(f"policy fixture is not implemented: {policy_name}")
