from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the launch should use the approved CPU settings")
def step_cpu_settings(context):
    raise StepNotImplementedError("CPU settings assertion is not implemented")
