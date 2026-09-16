from behave import then
from features.steps.support.lab_checks import LabChecks


@then(
    "the evidence index should distinguish current connection state from the "
    "acceptance snapshot"
)
def step_cpu_address_evidence_semantics(context):
    LabChecks(context).assert_cpu_address_evidence_semantics()
