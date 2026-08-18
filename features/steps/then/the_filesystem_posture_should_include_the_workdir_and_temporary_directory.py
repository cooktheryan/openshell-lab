from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the filesystem posture should include the workdir and temporary directory")
def step_baseline_filesystem_paths(context):
    LabChecks(context).assert_baseline_filesystem_posture()
