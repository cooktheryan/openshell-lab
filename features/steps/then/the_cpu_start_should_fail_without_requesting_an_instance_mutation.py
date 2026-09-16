from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the CPU start should fail without requesting an instance mutation")
def step_cpu_start_rejected(context):
    LabChecks(context).assert_cpu_start_rejected_before_mutation()
