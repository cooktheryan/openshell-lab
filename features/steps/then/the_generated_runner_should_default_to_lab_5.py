from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the generated runner should default to Lab 5")
def step_generated_runner_defaults_to_lab5(context):
    LabChecks(context).assert_generated_runner_defaults_to_lab5()
