import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, project_picker, show_api_error

page_header("Prompt Registry", "Every save creates a new numbered version. Old versions are never changed.")
project = project_picker("reg_project")

try:
    prompts = api.list_prompts(project["id"])["items"]
except ApiError as err:
    show_api_error(err)
    st.stop()
if not prompts:
    st.info("No prompts in this project yet. Run a prompt in the Playground and choose "
            "'Save as prompt asset'.")
    st.stop()

by_name = {p["name"]: p for p in prompts}
prompt = by_name[st.selectbox("Prompt", list(by_name))]
try:
    versions = api.list_prompt_versions(prompt["id"])
except ApiError as err:
    show_api_error(err)
    st.stop()

st.caption(f"{len(versions)} version(s). Newest first.")
st.dataframe(
    pd.DataFrame([{
        "version": v["version"], "created": v["created_at"][:19], "by": v["created_by"],
        "provider": v["provider"], "model": v["model"], "temperature": v["temperature"],
        "change": v["change_description"] or "", "experiments": len(v["evaluation_results"]),
    } for v in versions]),
    width="stretch", hide_index=True,
)

tab_view, tab_cmp, tab_new = st.tabs(["View / restore", "Compare", "New version"])
numbers = [v["version"] for v in versions]

with tab_view:
    n = st.selectbox("Version", numbers, key="view_ver")
    v = next(x for x in versions if x["version"] == n)
    st.code(v["template"], language="text")
    if v["system_instruction"]:
        st.markdown("**System instruction**")
        st.code(v["system_instruction"], language="text")
    st.caption(f"Variables: {', '.join(v['variables']) or 'none'} · max tokens {v['max_output_tokens']}")
    if v["evaluation_results"]:
        st.markdown("**Evaluation results (from experiments)**")
        for e in v["evaluation_results"]:
            bits = []
            for k, m in e["metrics"].items():
                text = f"{k}: mean {m['mean_score']}"
                if m["pass_rate"] is not None:
                    text += f", pass {m['pass_rate']:.0%}"
                bits.append(text)
            st.write(f"• **{e['name']}** ({e['status']}) — " + ("; ".join(bits) or "no evaluators"))
    if st.button(f"Restore version {n} as a new version", key="restore"):
        try:
            out = api.restore_prompt_version(prompt["id"], n)
            st.success(f"Created version {out['version']} from version {n}. History is unchanged.")
        except ApiError as err:
            show_api_error(err)

with tab_cmp:
    if len(numbers) < 2:
        st.info("Save at least two versions to compare them.")
    else:
        c1, c2 = st.columns(2)
        a = c1.selectbox("Version A", numbers, index=len(numbers) - 1, key="cmp_a")
        b = c2.selectbox("Version B", numbers, index=0, key="cmp_b")
        if a == b:
            st.info("Choose two different versions.")
        else:
            try:
                cmp = api.compare_prompt_versions(prompt["id"], a, b)
            except ApiError as err:
                show_api_error(err)
                st.stop()
            rows = [{"field": f, f"v{a}": str(c["a"]), f"v{b}": str(c["b"]),
                     "changed": "yes" if c["changed"] else ""} for f, c in cmp["changes"].items()]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            for field, lines in cmp["diffs"].items():
                if lines:
                    st.markdown(f"**{field} diff**")
                    st.code("\n".join(lines), language="diff")

with tab_new:
    latest = versions[0]
    with st.form("new_version"):
        template = st.text_area("Prompt template", latest["template"], height=150)
        system = st.text_area("System instruction", latest["system_instruction"] or "", height=70)
        c1, c2, c3 = st.columns(3)
        provider = c1.text_input("Provider", latest["provider"])
        model = c2.text_input("Model", latest["model"])
        temperature = c3.number_input("Temperature", 0.0, 2.0, float(latest["temperature"]), 0.05)
        max_tokens = st.number_input("Max output tokens", 1, 8192, int(latest["max_output_tokens"]), 64)
        change = st.text_input("Change description", max_chars=500)
        if st.form_submit_button("Save new version", type="primary"):
            try:
                out = api.add_prompt_version(prompt["id"], {
                    "template": template, "system_instruction": system or None, "provider": provider,
                    "model": model, "temperature": temperature, "max_output_tokens": int(max_tokens),
                    "change_description": change or None})
                st.success(f"Saved version {out['version']}.")
            except ApiError as err:
                show_api_error(err)
