import json

import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import api_key_input, page_header, pill, project_picker, show_api_error

page_header("Experiments", "Run a prompt version over a dataset version and score every answer.")
project = project_picker("exp_project")
tab_run, tab_hist, tab_cmp = st.tabs(["Run", "History", "Compare"])


def metrics_table(summary: dict) -> pd.DataFrame:
    rows = [{"metric": k, "kind": "objective" if m["kind"] == "objective" else "model judgment",
             "mean score": m["mean_score"], "pass rate": m["pass_rate"], "scored": m["n_scored"],
             "unscored": m["n_unscored"]} for k, m in summary.get("metrics", {}).items()]
    return pd.DataFrame(rows)


def show_summary(e: dict) -> None:
    s = e["summary"]
    ok = e["status"] == "completed"
    st.markdown(f"**{e['name']}** " + pill(e["status"], "ok" if ok else "bad"), unsafe_allow_html=True)
    a, b, c, d = st.columns(4)
    a.metric("Rows run", f"{s['rows_run']} / {s['rows_planned']}")
    b.metric("Failed", s["failed"])
    c.metric("Avg latency (ms)", f"{s['avg_latency_ms']:,.0f}" if s["avg_latency_ms"] else "n/a")
    d.metric("Tokens", f"{s['total_tokens']:,}")
    if e.get("abort_reason"):
        st.warning(f"Run stopped early: {e['abort_reason']}. Remaining rows were not sent.")
    df = metrics_table(s)
    if len(df):
        st.dataframe(df, width="stretch", hide_index=True)
        if (df["kind"] == "model judgment").any():
            st.caption("Model-judgment scores are opinions from another model, not measurements. "
                       "See the Evaluations page for limitations.")
    st.caption(f"Prompt v{e['prompt_version']} · dataset v{e['dataset_version']} ({e['split']}) · "
               f"{e['config']['provider']} / {e['config']['model']} · temp {e['config']['temperature']}")


def results_table(exp_id: str) -> None:
    res = api.experiment_results(exp_id)["items"]
    rows = []
    for r in res:
        row = {"#": r["row_index"], "input": json.dumps(r["input"], ensure_ascii=False)[:120],
               "output": (r["output"] or "")[:200], "status": r["status"],
               "latency ms": r["latency_ms"], "error": r["error_category"] or ""}
        for ev in r["evaluations"]:
            row[ev["name"]] = ev["score"]
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with st.expander("Evaluator details per row"):
        for r in res:
            for ev in r["evaluations"]:
                st.write(f"Row {r['row_index']} · {ev['name']}: {ev['detail']}")


with tab_run:
    try:
        prompts = api.list_prompts(project["id"])["items"]
        datasets = api.list_datasets(project["id"])["items"]
        evaluators = api.list_evaluators()
    except ApiError as err:
        show_api_error(err)
        st.stop()
    if not prompts or not datasets:
        st.info("You need at least one saved prompt and one dataset in this project.")
        st.stop()

    pmap = {p["name"]: p for p in prompts}
    dmap = {d["name"]: d for d in datasets}
    c1, c2 = st.columns(2)
    prompt = pmap[c1.selectbox("Prompt", list(pmap))]
    pver = c1.selectbox("Prompt version", range(prompt["latest_version"], 0, -1))
    dataset = dmap[c2.selectbox("Dataset", list(dmap))]
    dver = c2.selectbox("Dataset version", range(dataset["latest_version"], 0, -1))
    try:
        dv = next(v for v in api.list_dataset_versions(dataset["id"]) if v["version"] == dver)
        pv = next(v for v in api.list_prompt_versions(prompt["id"]) if v["version"] == pver)
    except (ApiError, StopIteration):
        st.error("Could not load those versions.")
        st.stop()
    fields = [f["name"] for f in dv["schema"]]
    missing = [v for v in pv["variables"] if v not in fields]
    if missing:
        st.warning(f"This prompt uses field(s) the dataset does not have: {', '.join(missing)}.")

    c3, c4, c5 = st.columns(3)
    split = c3.selectbox("Rows to use", ["all", *dv["split_counts"]])
    max_rows = c4.number_input("Max rows", 1, 500, 10,
                               help="Each row is one model call and may cost money. The server caps this.")
    ref = c5.selectbox("Reference answer column", ["(none)", *fields])
    exp_name = st.text_input("Experiment name", value=f"{prompt['name']} v{pver}", max_chars=100)

    st.markdown("**Evaluation metrics**")
    labels = {e["type"]: e for e in evaluators}
    chosen = st.multiselect("Metrics", list(labels), format_func=lambda t: (
        f"{t} {'(model judgment)' if labels[t]['kind'] != 'objective' else ''}"
        f"{' · needs reference' if labels[t]['needs_reference'] else ''}"))
    configs = []
    for t in chosen:
        info = labels[t]
        st.caption(f"**{t}** — {info['description']}  \n_Limitation: {info['limitations']}_")
        params = {}
        if t == "exact_match":
            params["case_sensitive"] = st.checkbox("Case sensitive", key=f"{t}_cs")
        elif t == "text_similarity":
            params["threshold"] = st.slider("Pass threshold", 0.0, 1.0, 0.8, 0.05, key=f"{t}_th")
        elif t == "json_valid":
            raw = st.text_area("JSON Schema (optional)", key=f"{t}_schema", height=80)
            if raw.strip():
                try:
                    params["schema"] = json.loads(raw)
                except ValueError:
                    st.error("That schema is not valid JSON.")
        elif t == "contains_keywords":
            params["keywords"] = [k.strip() for k in st.text_input(
                "Keywords (comma separated)", key=f"{t}_kw").split(",") if k.strip()]
            params["mode"] = st.radio("Match", ["all", "any"], horizontal=True, key=f"{t}_mode")
        elif t == "max_length":
            params["max_chars"] = int(st.number_input("Max characters", 1, 100000, 500, key=f"{t}_max"))
        elif t == "llm_judge":
            params["rubric"] = st.text_area("Rubric (what makes a good answer?)", key=f"{t}_rub", height=80)
            params["pass_score"] = int(st.slider("Pass score (1-5)", 1, 5, 4, key=f"{t}_ps"))
            st.warning("The judge makes extra model calls (extra cost) and gives an opinion, "
                       "not a measurement.")
        configs.append({"type": t, "params": params})

    provider_info = next((p for p in api.list_models()["providers"] if p["id"] == pv["provider"]), None)
    key = None
    if provider_info and pv["provider"] != "mock":
        key = api_key_input(pv["provider"], provider_info["label"],
                            provider_info["server_key_configured"], "exp")
    st.caption(f"Will use the model saved in the prompt version: {pv['provider']} / {pv['model']}.")
    if st.button("Run experiment", type="primary", disabled=not exp_name.strip() or bool(missing)):
        body = {"project_id": project["id"], "name": exp_name, "prompt_id": prompt["id"],
                "prompt_version": pver, "dataset_id": dataset["id"], "dataset_version": dver,
                "split": split, "max_rows": int(max_rows), "evaluators": configs,
                "reference_field": None if ref == "(none)" else ref}
        with st.spinner("Running... each row is a model call, so this can take a while."):
            try:
                exp = api.run_experiment(body, api_key=key)
            except ApiError as err:
                show_api_error(err)
                st.stop()
        show_summary(exp)
        results_table(exp["id"])

with tab_hist:
    try:
        exps = api.list_experiments(project["id"])["items"]
    except ApiError as err:
        show_api_error(err)
        st.stop()
    if not exps:
        st.info("No experiments yet.")
    else:
        emap = {f"{e['name']} · {e['created_at'][:16]}": e for e in exps}
        e = emap[st.selectbox("Experiment", list(emap))]
        show_summary(e)
        results_table(e["id"])

with tab_cmp:
    try:
        exps = api.list_experiments(project["id"])["items"]
    except ApiError as err:
        show_api_error(err)
        st.stop()
    emap = {f"{e['name']} · {e['created_at'][:16]}": e for e in exps}
    picked = st.multiselect("Choose 2 to 4 experiments", list(emap), max_selections=4)
    if len(picked) >= 2:
        try:
            cmp = api.compare_experiments([emap[p]["id"] for p in picked])
        except ApiError as err:
            show_api_error(err)
            st.stop()
        names = {e["id"]: e["name"] for e in cmp["experiments"]}
        st.markdown("**Metrics**")
        mrows = []
        for e in cmp["experiments"]:
            row = {"experiment": e["name"], "status": e["status"],
                   "avg latency ms": e["summary"]["avg_latency_ms"], "tokens": e["summary"]["total_tokens"]}
            for k, m in e["summary"]["metrics"].items():
                row[f"{k} (mean)"] = m["mean_score"]
            mrows.append(row)
        st.dataframe(pd.DataFrame(mrows), width="stretch", hide_index=True)
        if cmp["config_differences"]:
            st.markdown("**What differs between these runs**")
            st.dataframe(pd.DataFrame(cmp["config_differences"], index=list(names.values())).T,
                         width="stretch")
        if cmp["aligned"]:
            st.markdown("**Side-by-side outputs**")
            for r in cmp["rows"]:
                with st.expander(f"Row {r['row_index']}: {json.dumps(r['input'], ensure_ascii=False)[:90]}"):
                    cols = st.columns(len(cmp["experiments"]))
                    for col, e in zip(cols, cmp["experiments"], strict=True):
                        out = r["outputs"].get(e["id"])
                        col.markdown(f"**{e['name']}**")
                        if out:
                            col.write(out["output"] or f"_error: {out['error_category']}_")
                            for ev in out["evaluations"]:
                                col.caption(f"{ev['name']}: {ev['score']} ({ev['detail']})")
        else:
            st.info("These runs used different dataset versions or splits, so rows cannot be lined up. "
                    "Only summary metrics are compared.")
    else:
        st.info("Pick at least two experiments.")
