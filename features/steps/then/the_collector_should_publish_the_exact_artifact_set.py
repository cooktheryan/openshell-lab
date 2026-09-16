from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the collector should publish the exact artifact set")
def step_exact_archive_member_occurrences(context):
    LabChecks(context).assert_exact_archive_member_occurrences()
