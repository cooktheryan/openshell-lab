from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the selected evidence should be ordered from newest to oldest")
def step_merge_order(context):
    LabChecks(context).assert_merge_order()
