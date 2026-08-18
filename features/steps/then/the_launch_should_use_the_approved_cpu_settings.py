from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the launch should use the approved CPU settings")
def step_cpu_settings(context):
    LabChecks(context).assert_cpu_settings()
