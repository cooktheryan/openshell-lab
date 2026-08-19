from behave import then
from features.steps.support.lab_checks import LabChecks


@then('the filesystem action should be "{status}"')
def step_filesystem_status(context, status):
    LabChecks(context).assert_filesystem_action(status)
