from behave import given
from features.steps.support.lab_checks import LabChecks


@given('merge evidence is "{state}"')
def step_merge_evidence(context, state):
    LabChecks(context).load_merge_evidence(state)
