from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the CPU collector should reject concurrency and preserve prior evidence")
def step_cpu_publication_lock(context):
    LabChecks(context).assert_cpu_publication_lock()
