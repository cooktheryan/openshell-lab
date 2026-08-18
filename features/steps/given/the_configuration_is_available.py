from behave import given
from features.steps.support.lab_checks import LabChecks


@given('the "{configuration}" configuration is available')
def step_configuration_available(context, configuration):
    LabChecks(context).load_configuration(configuration)
