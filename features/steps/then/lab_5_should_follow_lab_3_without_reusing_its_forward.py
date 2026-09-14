from behave import then
from features.steps.support.lab_checks import LabChecks


@then("Lab 5 should follow Lab 3 without reusing its forward")
def step_lab5_cpu_sequence(context):
    LabChecks(context).assert_cpu_lab5_sequence()
