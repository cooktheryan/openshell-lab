from behave import then
from features.steps.support.lab_checks import LabChecks


@then("Lab 4 should follow Lab 3 without invoking Lab 5")
def step_lab4_cpu_sequence(context):
    LabChecks(context).assert_cpu_lab4_sequence()
