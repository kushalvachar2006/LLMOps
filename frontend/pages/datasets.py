import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, project_picker, show_api_error

page_header("Datasets", "Upload CSV or JSONL files. Each upload becomes an immutable version.")
project = project_picker("ds_project")

try:
    datasets = api.list_datasets(project["id"])["items"]
except ApiError as err:
    show_api_error(err)
    st.stop()
existing = {d["name"]: d for d in datasets}

with st.expander("Upload a dataset", expanded=not datasets):
    NEW = "New dataset"
    target = st.selectbox("Upload as", [NEW, *existing], key="ds_target")
    name = st.text_input("Dataset name", max_chars=100) if target == NEW else ""
    desc = st.text_input("Description (optional)", max_chars=500) if target == NEW else ""
    file = st.file_uploader("File (.csv or .jsonl, up to about 2 MB)", type=["csv", "jsonl", "ndjson"])
    required = st.text_input("Required fields (comma separated, optional)",
                             help="Every row must have a non-empty value for each of these.")
    split_mode = st.radio("Train / validation / eval split",
                          ["None", "Random split", "Use a 'split' column in the file"], horizontal=True)
    ratios, seed = None, 42
    if split_mode == "Random split":
        c1, c2, c3, c4 = st.columns(4)
        tr = c1.number_input("Train", 0.0, 1.0, 0.7, 0.05)
        va = c2.number_input("Validation", 0.0, 1.0, 0.15, 0.05)
        ev = c3.number_input("Eval", 0.0, 1.0, 0.15, 0.05)
        seed = int(c4.number_input("Seed", 0, 10_000, 42))
        ratios = {"train": tr, "validation": va, "eval": ev}
    change = st.text_input("Change description (optional)", max_chars=500, key="ds_change")
    if st.button("Upload", type="primary", disabled=file is None or (target == NEW and not name.strip())):
        try:
            text = file.getvalue().decode("utf-8-sig")
        except UnicodeDecodeError:
            st.error("The file is not UTF-8 text. Please save it as UTF-8 and try again.")
            st.stop()
        body = {"filename": file.name, "content": text,
                "required_fields": [f.strip() for f in required.split(",") if f.strip()],
                "split_ratios": ratios, "split_seed": seed, "change_description": change or None}
        try:
            if target == NEW:
                out = api.create_dataset({**body, "project_id": project["id"], "name": name,
                                          "description": desc})
                st.success(f"Dataset '{name}' created with {out['version']['row_count']} rows.")
            else:
                out = api.add_dataset_version(existing[target]["id"], body)
                st.success(f"Saved version {out['version']} ({out['row_count']} rows).")
        except ApiError as err:
            show_api_error(err)

if not datasets:
    st.info("No datasets in this project yet.")
    st.stop()

ds = existing[st.selectbox("Dataset", list(existing), key="ds_view")]
try:
    versions = api.list_dataset_versions(ds["id"])
except ApiError as err:
    show_api_error(err)
    st.stop()
st.dataframe(pd.DataFrame([{
    "version": v["version"], "file": v["filename"], "format": v["format"], "rows": v["row_count"],
    "splits": ", ".join(f"{k}: {n}" for k, n in v["split_counts"].items()),
    "created": v["created_at"][:19], "change": v["change_description"] or "",
} for v in versions]), width="stretch", hide_index=True)

num = st.selectbox("Inspect version", [v["version"] for v in versions])
ver = next(v for v in versions if v["version"] == num)
st.markdown("**Schema**")
st.dataframe(pd.DataFrame(ver["schema"]), width="stretch", hide_index=True)
st.caption(f"Content fingerprint (SHA-256): `{ver['content_sha256'][:16]}...`")
split = st.selectbox("Preview split", ["all", *ver["split_counts"]], key="ds_split")
try:
    rows = api.dataset_rows(ds["id"], num, split)
    st.dataframe(pd.DataFrame([{"#": r["index"], "split": r["split"], **r["data"]} for r in rows["items"]]),
                 width="stretch", hide_index=True)
    st.caption(f"Showing {len(rows['items'])} of {rows['total']} rows.")
except ApiError as err:
    show_api_error(err)
