from behave import when
from behave.api.pending_step import StepNotImplementedError


@when('the "{subject}" is evaluated')
def step_evaluate_subject(context, subject):
    raise StepNotImplementedError(f"evaluation is not implemented: {subject}")
