from behave import when
from features.steps.support.lab_checks import LabChecks


@when('the report agent writes beneath "{path}"')
def step_filesystem_write(context, path):
    LabChecks(context).evaluate_filesystem_write(path)
