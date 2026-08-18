from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the image identity should be non-root")
def step_non_root_image(context):
    LabChecks(context).assert_nonroot_image()
