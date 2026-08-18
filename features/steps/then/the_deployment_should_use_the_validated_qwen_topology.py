from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the deployment should use the validated Qwen topology")
def step_qwen_topology(context):
    raise StepNotImplementedError("GPU topology assertion is not implemented")
