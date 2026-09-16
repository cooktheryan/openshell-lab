from behave import given
from features.steps.support.lab_checks import LabChecks


@given('a saved CPU instance with valid project tags and type "{instance_type}"')
def step_saved_cpu_instance(context, instance_type):
    LabChecks(context).load_cpu_instance(instance_type)
