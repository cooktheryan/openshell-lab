from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the artifact should be excluded")
def step_artifact_excluded(context):
    raise StepNotImplementedError("artifact exclusion assertion is not implemented")
