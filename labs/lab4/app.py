"""OpenShell Lab 4: a protected Streamlit client for managed inference."""

import asyncio
import sys

import streamlit as st

from openshell_lab.streamlit_inference import (
    MAX_HISTORY_MESSAGES,
    MAX_PROMPT_CHARS,
    append_bounded_history,
    call_managed_inference,
    public_error_message,
)


SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are the OpenShell Lab 4 assistant. Explain security controls "
        "clearly and do not claim access to credentials, tools, or hosts."
    ),
}


st.set_page_config(page_title="OpenShell Lab 4", page_icon="🛡️", layout="wide")
st.title("OpenShell Lab 4")
st.caption("Containerized Streamlit with credential-free OpenShell managed inference")

st.sidebar.header("Active control layers")
st.sidebar.markdown(
    """
- **Filesystem:** application code is read-only; runtime state stays in `/tmp`.
- **Network:** ordinary egress is denied by default.
- **Process:** the workload runs as UID/GID `1500:1500` with hardened privileges.
- **Provider:** OpenShell owns the model route and credential outside the app.
"""
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input(
    "Ask about OpenShell's security controls",
    max_chars=MAX_PROMPT_CHARS,
)
if prompt is not None:
    st.session_state.messages = append_bounded_history(
        st.session_state.messages,
        {"role": "user", "content": prompt},
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    # The managed client accepts at most 20 messages, including the system
    # message, so the newest 19 conversation messages are sent on each turn.
    request_messages = [
        SYSTEM_MESSAGE,
        *st.session_state.messages[-(MAX_HISTORY_MESSAGES - 1) :],
    ]
    try:
        with st.spinner("OpenShell managed inference is responding…"):
            response = asyncio.run(call_managed_inference(request_messages))
    except Exception as error:
        print(
            f"managed inference failure: {type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        st.error(public_error_message(error))
    else:
        st.session_state.messages = append_bounded_history(
            st.session_state.messages,
            {"role": "assistant", "content": response},
        )
        with st.chat_message("assistant"):
            st.markdown(response)
