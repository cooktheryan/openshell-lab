from behave import when
from features.steps.support.lab_checks import LabChecks


@when("the report agent validates the Markdown")
def step_validate_markdown(context):
    LabChecks(context).validate_report()
