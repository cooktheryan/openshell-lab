from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the denied GitHub probe should be bounded and precede one report agent execution")
def step_lab3_deny_to_allow_transition(context):
    LabChecks(context).assert_lab3_deny_to_allow_transition()
