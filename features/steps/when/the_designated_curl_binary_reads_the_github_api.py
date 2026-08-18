from behave import when
from features.steps.support.lab_checks import LabChecks


@when("the designated curl binary reads the GitHub API")
def step_curl_reads_github(context):
    LabChecks(context).evaluate_designated_github_read()
