import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, pill, project_picker, show_api_error

page_header("Evaluations", "How answers are scored, and what each score can and cannot tell you.")
st.warning("No automatic metric proves an answer is factually correct, and no automated check "
           "can promise to catch every hallucination. Use scores to find answers worth reviewing.")

try:
    evaluators = api.list_evaluators()
except ApiError as err:
    show_api_error(err)
    st.stop()

st.markdown("### Available metrics")
for e in evaluators:
    kind = pill("objective", "ok") if e["kind"] == "objective" else pill("model judgment", "bad")
    st.markdown(f"**{e['type']}** {kind}" + (" · needs a reference answer" if e["needs_reference"] else ""),
                unsafe_allow_html=True)
    st.write(e["description"])
    st.caption(f"Limitation: {e['limitations']}")

st.divider()
st.markdown("### Results by experiment")
project = project_picker("ev_project")
try:
    exps = api.list_experiments(project["id"])["items"]
except ApiError as err:
    show_api_error(err)
    st.stop()
if not exps:
    st.info("Run an experiment with metrics selected to see results here.")
    st.stop()
rows = []
for e in exps:
    for name, m in e.get("summary", {}).get("metrics", {}).items():
        rows.append({"experiment": e["name"], "metric": name,
                     "kind": "objective" if m["kind"] == "objective" else "model judgment",
                     "mean score": m["mean_score"], "pass rate": m["pass_rate"],
                     "scored": m["n_scored"], "unscored": m["n_unscored"],
                     "prompt version": e["prompt_version"], "dataset version": e["dataset_version"]})
if rows:
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("Your experiments have no metrics yet. Choose metrics when running one.")
