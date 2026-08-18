from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the selected evidence should contain five unique merged pull requests")
def step_five_unique_merges(context):
    raise StepNotImplementedError("merge count assertion is not implemented")
