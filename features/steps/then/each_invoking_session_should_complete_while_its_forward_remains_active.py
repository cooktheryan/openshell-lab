from behave import then
from features.steps.support.lab_checks import LabChecks


@then("each invoking session should complete while its forward remains active")
def step_forwarded_session_completion(context):
    LabChecks(context).assert_forwarded_launchers_release_session()
