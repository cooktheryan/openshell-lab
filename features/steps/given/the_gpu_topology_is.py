from behave import given
from features.steps.support.lab_checks import LabChecks


@given('the GPU topology is "{topology}"')
def step_gpu_topology(context, topology):
    LabChecks(context).load_gpu_topology(topology)
