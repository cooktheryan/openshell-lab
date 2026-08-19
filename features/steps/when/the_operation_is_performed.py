from behave import when
from features.steps.support.lab_checks import LabChecks


@when('the "{operation}" operation is performed')
def step_operation(context, operation):
    LabChecks(context).perform_operation(operation)
