from behave import given
from features.steps.support.lab_checks import LabChecks


@given('the Streamlit prompt is "{prompt_state}"')
def step_streamlit_prompt(context, prompt_state):
    LabChecks(context).load_streamlit_prompt(prompt_state)
