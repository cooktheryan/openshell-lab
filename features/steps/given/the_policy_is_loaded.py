from behave import given
from features.steps.support.lab_checks import LabChecks


@given('the "{policy_name}" policy is loaded')
def step_policy_loaded(context, policy_name):
    LabChecks(context).load_policy(policy_name)
