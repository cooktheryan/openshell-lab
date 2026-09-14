from behave import then
from features.steps.support.lab_checks import LabChecks


@then('the maximum concurrent sequence limit should be "{maximum_sequences}"')
def step_maximum_sequence_limit(context, maximum_sequences):
    LabChecks(context).assert_gpu_sequence_limit(maximum_sequences)
