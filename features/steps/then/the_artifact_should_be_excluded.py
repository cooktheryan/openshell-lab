from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the artifact should be excluded")
def step_artifact_excluded(context):
    LabChecks(context).assert_artifact_excluded()
