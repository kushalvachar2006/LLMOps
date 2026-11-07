import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, pill, show_api_error

page_header("Overview", "Live status and metrics derived from stored request records.")

try:
    h = api.health()
except ApiError as err:
    show_api_error(err)
    st.stop()

c1, c2, c3 = st.columns(3)
c1.markdown("**API**<br>" + pill("Up", "ok"), unsafe_allow_html=True)
db_up = h["database"]["status"] == "up"
c2.markdown("**Database**<br>" + pill("Up" if db_up else "Down", "ok" if db_up else "bad"),
            unsafe_allow_html=True)
c3.markdown(f"**LLM provider**<br>`{h['llm_provider']}`", unsafe_allow_html=True)
st.divider()

if not db_up:
    st.warning("MongoDB is unreachable, so metrics cannot be loaded.")
    st.stop()

try:
    page = api.list_requests(limit=100)
    projects = api.list_projects(limit=1)
except ApiError as err:
    show_api_error(err)
    st.stop()

items = page["items"]
m1, m2 = st.columns(2)
m1.metric("Total requests", page["total"])
m2.metric("Projects", projects["total"])

if not items:
    st.info("No requests recorded yet. Run a prompt in the Prompt Playground to see data here.")
    st.stop()

df = pd.DataFrame(items)
ok = df[df["status"] == "success"]
st.caption(f"Statistics below cover the latest {len(df)} requests.")
a, b, c, d = st.columns(4)
a.metric("Succeeded", len(ok))
b.metric("Failed", len(df) - len(ok))
b_lat = ok["latency_ms"].mean() if len(ok) else None
c.metric("Avg latency (ms)", f"{b_lat:,.0f}" if b_lat is not None else "n/a")
tok = ok["total_tokens"].dropna().sum() if len(ok) else 0
d.metric("Tokens used", f"{int(tok):,}")

st.markdown("#### Recent requests")
cols = ["created_at", "status", "provider", "model", "latency_ms", "total_tokens", "error_category"]
st.dataframe(df[cols], width="stretch", hide_index=True)
