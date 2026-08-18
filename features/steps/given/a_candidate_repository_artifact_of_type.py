from behave import given
from behave.api.pending_step import StepNotImplementedError


@given('a candidate repository artifact of type "{artifact_type}"')
def step_candidate_artifact(context, artifact_type):
    raise StepNotImplementedError(f"artifact fixture is not implemented: {artifact_type}")
