from behave import then
from features.steps.support.lab_checks import LabChecks


@then('the report validation should be "{status}"')
def step_report_status(context, status):
    LabChecks(context).assert_report_status(status)
