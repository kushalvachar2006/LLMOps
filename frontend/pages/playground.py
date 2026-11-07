import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.feedback import rate_response
from components.ui import api_key_input, page_header, show_api_error

page_header("Prompt Playground", "Pick any provider and model, bring your own API key, and run a prompt.")

try:
    catalog = api.list_models()
except ApiError as err:
    show_api_error(err)
    st.stop()

PROVIDERS = {p["label"]: p for p in catalog["providers"]}
CUSTOM = "Custom model ID..."


def config_form(prefix: str, title: str) -> dict:
    """One model configuration. Returns a dict ready to send to the backend."""
    st.markdown(f"**{title}**")
    labels = list(PROVIDERS)
    default = next((p["label"] for p in PROVIDERS.values() if p["id"] == catalog["default_provider"]),
                   labels[0])
    prov = PROVIDERS[st.selectbox("Provider", labels, index=labels.index(default), key=f"{prefix}_prov")]
    names = {m["id"]: m["label"] for m in prov["models"]}
    choice = st.selectbox("Model", [*names, CUSTOM], format_func=lambda x: names.get(x, x),
                          key=f"{prefix}_model_{prov['id']}")
    info = None
    if choice == CUSTOM:
        model_id = st.text_input("Custom model ID", key=f"{prefix}_custom_{prov['id']}").strip()
    else:
        model_id = choice
        info = next(m for m in prov["models"] if m["id"] == choice)
        if info["note"]:
            st.caption(info["note"])
    temp_max = info["temp_max"] if info else (1.0 if prov["id"] == "anthropic" else 2.0)
    supports_temp = info["supports_temperature"] if info else True
    temperature = st.slider("Temperature", 0.0, temp_max, min(0.7, temp_max), 0.05,
                            disabled=not supports_temp, key=f"{prefix}_temp_{prov['id']}_{model_id}")
    max_tokens = st.number_input("Max output tokens", 1, 8192, 1024, 64, key=f"{prefix}_max")
    system = st.text_area("System instruction (optional)", height=80, max_chars=5000, key=f"{prefix}_sys")
    key = None
    if prov["id"] != "mock":
        key = api_key_input(prov["id"], prov["label"], prov["server_key_configured"], prefix)
    return {"provider": prov["id"], "provider_label": prov["label"], "model": model_id,
            "temperature": temperature, "max_output_tokens": int(max_tokens),
            "system_instruction": system or None, "api_key": key}


def show_result(res: dict) -> None:
    st.write(res["text"] or "_The model returned no text._")
    u = res["usage"]
    a, b, c = st.columns(3)
    a.metric("Latency (ms)", f"{res['latency_ms']:,.0f}")
    b.metric("Tokens in / out", f"{u['input_tokens'] if u['input_tokens'] is not None else 'n/a'} / "
                                f"{u['output_tokens'] if u['output_tokens'] is not None else 'n/a'}")
    c.metric("Total tokens", u["total_tokens"] if u["total_tokens"] is not None else "n/a")
    st.caption(f"Request {res['request_id']} · {res['provider']} / {res['model']}")
    if not res["telemetry_recorded"]:
        st.warning("The answer was generated, but saving its telemetry failed. See backend logs.")


compare = st.toggle("Compare two configurations", help="Runs the same prompt on two setups.")
prompt = st.text_area("Prompt", height=170, max_chars=20000,
                      help="Use {{field}} placeholders if you plan to save this as a reusable prompt.")

cols = st.columns(2) if compare else [st.container()]
with cols[0]:
    cfg_a = config_form("a", "Configuration A" if compare else "Model settings")
cfg_b = None
if compare:
    with cols[1]:
        cfg_b = config_form("b", "Configuration B")

active = [c for c in (cfg_a, cfg_b) if c]
ready = bool(prompt.strip()) and all(c["model"] for c in active)
if st.button("Run", type="primary", disabled=not ready):
    results = []
    for cfg in active:
        payload = {"prompt": prompt, "provider": cfg["provider"], "model": cfg["model"],
                   "temperature": cfg["temperature"], "max_output_tokens": cfg["max_output_tokens"],
                   "system_instruction": cfg["system_instruction"]}
        with st.spinner(f"Running {cfg['provider_label']} / {cfg['model']}..."):
            try:
                results.append((cfg, api.generate(payload, api_key=cfg["api_key"]), None))
            except ApiError as err:
                results.append((cfg, None, err))
    st.session_state["pg_results"] = {"prompt": prompt, "items": results}

saved = st.session_state.get("pg_results")
if saved:
    st.markdown("#### Results")
    rcols = st.columns(len(saved["items"]))
    for idx, (col, (cfg, res, err)) in enumerate(zip(rcols, saved["items"], strict=True)):
        with col:
            st.markdown(f"**{cfg['provider_label']} · {cfg['model']}**")
            if err:
                show_api_error(err)
            else:
                show_result(res)
                rate_response(res["request_id"], f"fb_{idx}_{res['request_id']}")

    with st.expander("Save as prompt asset"):
        st.caption("Saves the prompt text and Configuration A as an immutable version.")
        try:
            projects = api.list_projects()["items"]
            existing = {}
        except ApiError:
            projects = []
        if not projects:
            st.info("Create a project first on the Projects page.")
        else:
            pmap = {p["name"]: p["id"] for p in projects}
            pname = st.selectbox("Project", list(pmap), key="save_proj")
            try:
                existing = {p["name"]: p["id"] for p in api.list_prompts(pmap[pname])["items"]}
            except ApiError:
                existing = {}
            mode = st.radio("Save as", ["New prompt", "New version of existing prompt"],
                            horizontal=True, disabled=not existing)
            with st.form("save_prompt"):
                if mode == "New prompt" or not existing:
                    name = st.text_input("Prompt name", max_chars=100)
                    target = None
                else:
                    target = existing[st.selectbox("Prompt", list(existing))]
                    name = ""
                change = st.text_input("Change description (optional)", max_chars=500)
                if st.form_submit_button("Save", type="primary"):
                    cfg = saved["items"][0][0]
                    body = {"template": saved["prompt"], "provider": cfg["provider"],
                            "model": cfg["model"], "temperature": cfg["temperature"],
                            "max_output_tokens": cfg["max_output_tokens"],
                            "system_instruction": cfg["system_instruction"],
                            "change_description": change or None}
                    try:
                        if target:
                            out = api.add_prompt_version(target, body)
                            st.success(f"Saved as version {out['version']}.")
                        else:
                            out = api.create_prompt({**body, "project_id": pmap[pname], "name": name})
                            st.success(f"Prompt '{name}' saved as version 1.")
                    except ApiError as err:
                        show_api_error(err)
