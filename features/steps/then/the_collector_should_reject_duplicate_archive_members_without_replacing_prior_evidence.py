from behave import then
from features.steps.support.lab_checks import LabChecks


@then(
    "the collector should reject duplicate archive members without replacing "
    "prior evidence"
)
def step_duplicate_archive_member_occurrences(context):
    LabChecks(context).assert_duplicate_archive_member_occurrences()
