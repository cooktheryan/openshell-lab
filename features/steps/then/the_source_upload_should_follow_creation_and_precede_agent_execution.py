from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the source upload should follow creation and precede agent execution")
def step_source_upload_ordering(context):
    LabChecks(context).assert_lab1_upload_ordering()
