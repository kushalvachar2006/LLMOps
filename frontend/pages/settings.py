import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, show_api_error

page_header("Settings", "Read-only view of how this app is connected.")
st.markdown(f"**Backend URL:** `{api.API_URL}` (set with the `API_URL` environment variable)")
try:
    h = api.health()
    st.json(h)
    if not h.get("admin_auth"):
        st.warning("The management API has no ADMIN_TOKEN, so anyone who can reach it can use it. "
                   "That is fine on your own laptop; set ADMIN_TOKEN before sharing or hosting.")
except ApiError as err:
    show_api_error(err)
st.caption("API keys live only on the backend. This page never shows or accepts them.")

st.markdown("#### Data handling (monitoring)")
try:
    pol = api.monitoring_policy()
    st.markdown(
        f"- **Prompt and response text stored:** {'yes' if pol['store_prompt_text'] else 'no (default)'}\n"
        f"- **Redaction of stored text:** {'on' if pol['redaction_enabled'] else 'off'}\n"
        f"- **Trace retention:** "
        f"{str(pol['retention_days']) + ' days' if pol['retention_days'] else 'kept until you delete them'}\n"
        f"- **Never stored:** {', '.join(pol['never_stored'])}\n"
        f"- **Time to first token:** {pol['streaming_first_token_time']}\n"
        f"- **Retries:** {pol['retries']}"
    )
except ApiError as err:
    show_api_error(err)
