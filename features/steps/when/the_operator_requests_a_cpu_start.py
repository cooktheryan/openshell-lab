from behave import when
from features.steps.support.lab_checks import LabChecks


@when("the operator requests a CPU start")
def step_request_cpu_start(context):
    LabChecks(context).request_cpu_start()
