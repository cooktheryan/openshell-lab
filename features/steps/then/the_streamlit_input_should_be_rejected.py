from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Streamlit input should be rejected")
def step_streamlit_input_rejected(context):
    LabChecks(context).assert_streamlit_input_rejected()
