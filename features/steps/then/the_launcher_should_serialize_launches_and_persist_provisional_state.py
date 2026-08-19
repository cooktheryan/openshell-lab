from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the launcher should serialize launches and persist provisional state")
def step_cpu_launch_safety(context):
    LabChecks(context).assert_cpu_launch_safety()
