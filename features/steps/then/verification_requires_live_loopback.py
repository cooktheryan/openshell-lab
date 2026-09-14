from behave import then
from features.steps.support.lab_checks import LabChecks


@then("verification should require a live loopback listener")
def step_lab5_verifier_live_listener(context):
    LabChecks(context).assert_lab5_live_listener_loopback_only()
