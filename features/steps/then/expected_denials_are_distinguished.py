from behave import then
from features.steps.support.lab_checks import LabChecks


@then("expected denials should be distinguished from operational failures")
def step_lab4_verifier_denials_fail_closed(context):
    LabChecks(context).assert_lab4_denials_fail_closed()
