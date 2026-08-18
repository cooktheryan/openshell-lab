from behave import when
from behave.api.pending_step import StepNotImplementedError


@when("the designated curl binary reads the GitHub API")
def step_curl_reads_github(context):
    raise StepNotImplementedError("GitHub policy evaluation is not implemented")
