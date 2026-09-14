from behave import then
from features.steps.support.lab_checks import LabChecks


@then("the Streamlit conversation history should remain bounded")
def step_streamlit_history_bounded(context):
    LabChecks(context).assert_streamlit_history_bounded()
