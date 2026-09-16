from behave import then
from features.steps.support.lab_checks import LabChecks


@then(
    "the CPU collector should preserve prior evidence after complete scope "
    "validation"
)
def step_large_cpu_archive_scope(context):
    LabChecks(context).assert_large_cpu_archive_scope()
