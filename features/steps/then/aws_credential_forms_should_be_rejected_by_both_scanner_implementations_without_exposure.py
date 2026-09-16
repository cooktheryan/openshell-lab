from behave import then
from features.steps.support.lab_checks import LabChecks


@then(
    "AWS credential forms should be rejected by both scanner implementations "
    "without exposure"
)
def step_aws_credential_scanner_matrix(context):
    LabChecks(context).assert_aws_credential_scanner_matrix()
