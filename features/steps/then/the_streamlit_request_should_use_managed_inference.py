from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Streamlit request should use managed inference")
def step_streamlit_managed_request(context):
    LabChecks(context).assert_streamlit_managed_request()
