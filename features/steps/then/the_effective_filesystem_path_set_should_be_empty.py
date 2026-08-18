from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the effective filesystem path set should be empty")
def step_empty_filesystem_paths(context):
    LabChecks(context).assert_empty_filesystem_paths()
