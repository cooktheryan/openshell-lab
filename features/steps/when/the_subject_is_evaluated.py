from behave import when
from features.steps.support.lab_checks import LabChecks


@when('the "{subject}" is evaluated')
def step_evaluate_subject(context, subject):
    LabChecks(context).evaluate_subject(subject)
