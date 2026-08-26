from behave import then
from features.steps.support.lab_checks import LabChecks


@then("credential-bearing content should be rejected without exposing it")
def step_secret_scanner_fallback(context):
    LabChecks(context).assert_secret_scanner_fallback()
