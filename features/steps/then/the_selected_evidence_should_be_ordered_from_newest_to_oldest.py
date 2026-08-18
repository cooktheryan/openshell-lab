from behave import then
from behave.api.pending_step import StepNotImplementedError


@then("the selected evidence should be ordered from newest to oldest")
def step_merge_order(context):
    raise StepNotImplementedError("merge order assertion is not implemented")
