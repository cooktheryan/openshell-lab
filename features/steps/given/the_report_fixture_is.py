from behave import given
from features.steps.support.lab_checks import LabChecks


@given('the report fixture is "{state}"')
def step_report_fixture(context, state):
    LabChecks(context).load_report_fixture(state)
