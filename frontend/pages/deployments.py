import json

import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import api_key_input, page_header, pill, project_picker, show_api_error

page_header("Deployments", "Publish a validated prompt as a versioned endpoint that other apps can call.")
project = project_picker("dep_project")
ENVS = ["development", "staging", "production"]

try:
    deployments = api.list_deployments(project["id"])
except ApiError as err:
    show_api_error(err)
    st.stop()

tab_dep, tab_keys, tab_try = st.tabs(["Deployments", "API keys", "Try it"])


def status_pill(status: str) -> str:
    kind = {"ready": "ok", "healthy": "ok", "active": "ok", "failed": "bad", "unhealthy": "bad"}
    return pill(status, kind.get(status, "plan"))


def pick_deployment(key: str):
    if not deployments:
        return None
    names = {d["name"]: d for d in deployments}
    return names[st.selectbox("Deployment", list(names), key=key)]


# ======================= deployments =======================
with tab_dep:
    with st.expander("Create a deployment", expanded=not deployments):
        with st.form("create_dep", clear_on_submit=True):
            name = st.text_input("Name", max_chars=100)
            desc = st.text_input("Description (optional)", max_chars=500)
            if st.form_submit_button("Create", type="primary"):
                try:
                    api.create_deployment(project["id"], name, desc)
                    st.rerun()
                except ApiError as err:
                    show_api_error(err)
    dep = pick_deployment("dep_pick")
    if dep is None:
        st.info("Create your first deployment above.")
    else:
        st.markdown(f"**{dep['name']}** " + status_pill(dep["status"]) +
                    f" &nbsp; <span class='muted'>ID `{dep['id']}`</span>", unsafe_allow_html=True)
        cols = st.columns(3)
        for col, env in zip(cols, ENVS, strict=True):
            live = dep["environments"][env]
            col.metric(env.capitalize(), f"v{live}" if live else "nothing live")

        try:
            versions = api.list_deployment_versions(dep["id"])
            prompts = api.list_prompts(project["id"])["items"]
        except ApiError as err:
            show_api_error(err)
            st.stop()

        st.markdown("#### Publish a new version")
        st.caption("Publishing runs validation checks, including a real model call. A version only "
                   "becomes 'ready' if every check passes. These calls use tokens.")
        if not prompts:
            st.info("Save a prompt first (Prompt Playground, then 'Save as prompt asset').")
        else:
            pmap = {p["name"]: p for p in prompts}
            c1, c2 = st.columns(2)
            prompt = pmap[c1.selectbox("Prompt", list(pmap), key="pub_prompt")]
            pver = c2.selectbox("Prompt version", range(prompt["latest_version"], 0, -1), key="pub_pver")
            try:
                pv = next(v for v in api.list_prompt_versions(prompt["id"]) if v["version"] == pver)
            except (ApiError, StopIteration):
                st.error("Could not load that prompt version.")
                st.stop()
            st.caption(f"Model: {pv['provider']} / {pv['model']} · inputs the API will need: "
                       f"{', '.join(pv['variables']) or 'none'}")
            samples_raw = st.text_area(
                "Sample inputs (optional, JSON list of objects)", height=70, key="pub_samples",
                placeholder='[{"name": "Ada"}]',
                help="Used for the validation call. If empty, placeholder text is used.")
            c3, c4 = st.columns(2)
            expect_json = c3.checkbox("Output must be valid JSON", key="pub_json")
            max_chars = c4.number_input("Max output characters (0 = no limit)", 0, 100000, 0, key="pub_max")
            change = st.text_input("Change description (optional)", max_chars=500, key="pub_change")
            info = next((p for p in api.list_models()["providers"] if p["id"] == pv["provider"]), None)
            key = None
            if info and pv["provider"] != "mock":
                key = api_key_input(pv["provider"], info["label"], info["server_key_configured"], "dep")
            if st.button("Validate and publish", type="primary"):
                try:
                    samples = json.loads(samples_raw) if samples_raw.strip() else []
                    if not isinstance(samples, list) or not all(isinstance(s, dict) for s in samples):
                        raise ValueError
                except ValueError:
                    st.error("Sample inputs must be a JSON list of objects, for example "
                             '[{"name": "Ada"}].')
                    st.stop()
                payload = {"prompt_id": prompt["id"], "prompt_version": pver,
                           "change_description": change or None,
                           "validation": {"sample_inputs": samples, "expect_json": expect_json,
                                          "max_output_chars": int(max_chars) or None}}
                with st.spinner("Validating with a live model call..."):
                    try:
                        out = api.publish_version(dep["id"], payload, api_key=key)
                    except ApiError as err:
                        show_api_error(err)
                        st.stop()
                if out["status"] == "ready":
                    st.success(f"Version {out['version']} passed all checks and is ready to promote.")
                else:
                    st.error(f"Version {out['version']} failed validation and cannot be promoted.")
                st.dataframe(pd.DataFrame(out["validation_report"]["checks"]), width="stretch",
                             hide_index=True)

        st.markdown("#### Versions")
        if versions:
            st.dataframe(pd.DataFrame([{
                "version": v["version"], "prompt": f"{v['prompt_name']} v{v['prompt_version']}",
                "model": f"{v['config']['provider']} / {v['config']['model']}", "status": v["status"],
                "health": v["health"]["status"], "created": v["created_at"][:19],
                "note": v["change_description"] or "",
            } for v in versions]), width="stretch", hide_index=True)

            ready = [v["version"] for v in versions if v["status"] == "ready"]
            st.markdown("#### Promote to an environment")
            if not ready:
                st.info("No version has passed validation yet.")
            else:
                p1, p2 = st.columns(2)
                version = p1.selectbox("Version", ready, key="promo_version")
                env = p2.selectbox("Environment", ENVS, index=2, key="promo_env")
                confirm = True
                if env == "production":
                    confirm = st.checkbox("I understand this changes what live callers receive",
                                          key="promo_confirm")
                if st.button(f"Promote v{version} to {env}", disabled=not confirm, key="promo_go"):
                    try:
                        api.promote_version(dep["id"], version, env)
                        st.success(f"v{version} is now live in {env}. "
                                   "Choosing an older version later acts as a rollback.")
                        st.rerun()
                    except ApiError as err:
                        show_api_error(err)
            live_envs = [e for e in ENVS if dep["environments"][e]]
            if live_envs:
                u1, u2 = st.columns(2)
                stop_env = u1.selectbox("Take an environment offline", live_envs, key="unpub_env")
                if u2.button("Unpublish", key="unpub_go"):
                    try:
                        api.unpublish_environment(dep["id"], stop_env)
                        st.rerun()
                    except ApiError as err:
                        show_api_error(err)

            sel = st.selectbox("Inspect version", [v["version"] for v in versions], key="insp_version")
            v = next(x for x in versions if x["version"] == sel)
            health = v["health"]
            st.markdown(f"Status {status_pill(v['status'])} &nbsp; Health {status_pill(health['status'])}"
                        f" &nbsp; <span class='muted'>{health['detail']}</span>",
                        unsafe_allow_html=True)
            if v["validation_report"]:
                st.dataframe(pd.DataFrame(v["validation_report"]["checks"]), width="stretch",
                             hide_index=True)
            hkey = None
            hinfo = next((p for p in api.list_models()["providers"] if p["id"] == v["config"]["provider"]),
                         None)
            if hinfo and v["config"]["provider"] != "mock":
                hkey = api_key_input(v["config"]["provider"], hinfo["label"],
                                     hinfo["server_key_configured"], "hc")
            if st.button("Run health check now", key="hc_go"):
                try:
                    res = api.deployment_health_check(dep["id"], sel, api_key=hkey)
                    st.info(f"Health: {res['health']['status']} ({res['health']['detail']})")
                except ApiError as err:
                    show_api_error(err)

            live = dep["environments"]["production"] or dep["environments"]["staging"] or \
                dep["environments"]["development"]
            if live:
                lv = next(x for x in versions if x["version"] == live)
                example = {name: "..." for name in lv["variables"]}
                st.markdown("#### How other apps call this")
                st.code(
                    f'curl -X POST {api.API_URL}/v1/deployments/{dep["id"]}/invoke \\\n'
                    '  -H "Authorization: Bearer <YOUR_API_KEY>" \\\n'
                    '  -H "Content-Type: application/json" \\\n'
                    f"  -d '{json.dumps({'inputs': example, 'environment': 'production'})}'",
                    language="bash")
                st.caption("Create a key on the API keys tab. Callers never see your prompt, model "
                           "settings or any provider key.")

        st.markdown("#### Usage")
        try:
            use = api.deployment_usage(dep["id"])
            if use["empty"]:
                st.info("No calls recorded for this deployment in the last 7 days.")
            else:
                a, b, c, d = st.columns(4)
                a.metric("Calls", use["total"])
                b.metric("Error rate", f"{use['error_rate']:.1%}")
                c.metric("Avg latency", f"{use['avg_latency_ms']:,.0f} ms"
                         if use["avg_latency_ms"] is not None else "n/a")
                d.metric("Tokens", f"{use['input_tokens'] + use['output_tokens']:,}")
                st.dataframe(pd.DataFrame(use["by_version"]), width="stretch", hide_index=True)
                st.caption(use["note"])
        except ApiError as err:
            show_api_error(err)

        events = api.deployment_events(dep["id"])
        if events:
            st.markdown("#### History")
            st.dataframe(pd.DataFrame(events)[["at", "type", "environment", "from_version", "to_version"]],
                         width="stretch", hide_index=True)

# ======================= API keys =======================
with tab_keys:
    st.caption("Keys let other applications call this project's live deployments. A key only works "
               "for this project and the environments you choose.")
    fresh = st.session_state.get("new_api_key")
    if fresh:
        st.success(f"Key '{fresh['name']}' created. Copy it now: it will NOT be shown again.")
        st.code(fresh["secret"], language="text")
        if st.button("I have copied it", key="key_dismiss"):
            del st.session_state["new_api_key"]
            st.rerun()
    with st.form("create_key", clear_on_submit=True):
        k1, k2, k3 = st.columns([3, 3, 2])
        kname = k1.text_input("Key name", max_chars=100, placeholder="e.g. mobile app")
        kenvs = k2.multiselect("Allowed environments", ENVS, default=["production"])
        klimit = k3.number_input("Calls per minute", 1, 1000, 60)
        if st.form_submit_button("Create API key", type="primary", disabled=False):
            try:
                st.session_state["new_api_key"] = api.create_api_key({
                    "project_id": project["id"], "name": kname, "environments": kenvs,
                    "rate_limit_per_minute": int(klimit)})
                st.rerun()
            except ApiError as err:
                show_api_error(err)
    try:
        keys = api.list_api_keys(project["id"])
    except ApiError as err:
        show_api_error(err)
        keys = []
    if keys:
        st.dataframe(pd.DataFrame([{
            "name": k["name"], "key": k["prefix"] + "...", "environments": ", ".join(k["environments"]),
            "limit/min": k["rate_limit_per_minute"], "calls": k["request_count"],
            "last used": (k["last_used_at"] or "never")[:19],
            "status": "revoked" if k["revoked_at"] else "active"} for k in keys]),
            width="stretch", hide_index=True)
        active = {f"{k['name']} ({k['prefix']}...)": k for k in keys if not k["revoked_at"]}
        if active:
            r1, r2 = st.columns([3, 1])
            target = active[r1.selectbox("Revoke a key", list(active), key="revoke_pick")]
            sure = r1.checkbox("Yes, revoke it. Apps using it will stop working immediately.",
                               key="revoke_sure")
            if r2.button("Revoke", disabled=not sure, key="revoke_go"):
                try:
                    api.revoke_api_key(target["id"])
                    st.rerun()
                except ApiError as err:
                    show_api_error(err)
    else:
        st.info("No API keys yet for this project.")

# ======================= try it =======================
with tab_try:
    st.caption("Calls the real public endpoint, the same way an outside app would, using an API key.")
    dep2 = pick_deployment("try_pick")
    if dep2 is None:
        st.info("Create a deployment first.")
    else:
        live_envs = [e for e in ENVS if dep2["environments"][e]]
        if not live_envs:
            st.info("Nothing is live yet. Publish and promote a version first.")
        else:
            env2 = st.selectbox("Environment", live_envs, key="try_env")
            versions2 = api.list_deployment_versions(dep2["id"])
            lv = next(x for x in versions2 if x["version"] == dep2["environments"][env2])
            inputs = {name: st.text_input(f"Input: {name}", key=f"try_in_{name}")
                      for name in lv["variables"]}
            token = st.text_input("API key", type="password", key="try_token",
                                  help="Paste a key from the API keys tab. It is not stored.")
            if st.button("Call the endpoint", type="primary", disabled=not token.strip(), key="try_go"):
                try:
                    res = api.invoke_deployment(dep2["id"], inputs, env2, token.strip())
                    st.write(res["output"] or "_empty output_")
                    st.caption(f"Version {res['version']} · {res['latency_ms']:,.0f} ms · "
                               f"{res['usage']['total_tokens']} tokens · request {res['request_id']}")
                except ApiError as err:
                    show_api_error(err)
