from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the secret scan should fail without reporting clean")
def step_secret_search_failure(context):
    LabChecks(context).assert_secret_search_failure()
