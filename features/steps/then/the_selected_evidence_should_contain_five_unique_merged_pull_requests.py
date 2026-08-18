from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the selected evidence should contain five unique merged pull requests")
def step_five_unique_merges(context):
    LabChecks(context).assert_five_unique_merges()
