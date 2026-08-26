from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Lab 2 forward should stop before Lab 3 starts")
def step_cpu_forward_sequence(context):
    LabChecks(context).assert_cpu_forward_sequence()
