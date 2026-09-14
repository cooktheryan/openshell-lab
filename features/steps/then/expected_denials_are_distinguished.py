from behave import then
from features.steps.support.lab_checks import LabChecks


@then("expected denials should be distinguished from operational failures")
def step_lab5_verifier_denials_fail_closed(context):
    LabChecks(context).assert_lab5_denials_fail_closed()
