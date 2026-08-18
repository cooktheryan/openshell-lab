from behave import given
from features.steps.support.lab_checks import LabChecks


@given('a candidate repository artifact of type "{artifact_type}"')
def step_candidate_artifact(context, artifact_type):
    LabChecks(context).load_candidate_artifact(artifact_type)
