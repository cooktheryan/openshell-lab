from behave import then
from features.steps.support.lab_checks import LabChecks


@then("only explicitly referenced issues should be associated")
def step_explicit_issues(context):
    LabChecks(context).assert_explicit_issues()
