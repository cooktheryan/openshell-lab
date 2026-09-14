from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the GPU profile selection should be rejected")
def step_gpu_profile_rejected(context):
    LabChecks(context).assert_gpu_profile_rejected()
