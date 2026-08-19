from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the bootstrap should resolve and verify the latest stable release")
def step_latest_stable_release(context):
    LabChecks(context).assert_latest_openshell_release()
