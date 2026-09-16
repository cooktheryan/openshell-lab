from behave import then
from features.steps.support.lab_checks import LabChecks


@then(
    "the collector should preserve prior evidence after remote directory "
    "selection fails"
)
def step_remote_directory_selection_failure(context):
    LabChecks(context).assert_remote_directory_selection_failure()
