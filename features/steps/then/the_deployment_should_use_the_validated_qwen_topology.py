from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the deployment should use the validated Qwen topology")
def step_qwen_topology(context):
    LabChecks(context).assert_gpu_settings()
