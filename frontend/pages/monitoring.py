from datetime import UTC, date, datetime, timedelta

import pandas as pd
import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, pill, show_api_error

page_header("Monitoring", "Every number is computed from saved request, evaluation and feedback records.")

# ---------------- filters ----------------
try:
    projects = api.list_projects()["items"]
    catalog = api.list_models()
except ApiError as err:
    show_api_error(err)
    st.stop()

c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
pmap = {"All projects": None, **{p["name"]: p["id"] for p in projects}}
project_id = pmap[c1.selectbox("Project", list(pmap), key="mon_project")]
preset = c2.selectbox("Date range", ["Last 24 hours", "Last 7 days", "Last 30 days", "Custom"],
                      index=1, key="mon_range")
providers = {"All providers": None, **{p["label"]: p["id"] for p in catalog["providers"]}}
provider = providers[c3.selectbox("Provider", list(providers), key="mon_provider")]
model = c4.text_input("Model (optional)", key="mon_model").strip() or None

now = datetime.now(UTC)
if preset == "Custom":
    today = date.today()
    picked = st.date_input("Custom range (UTC dates)", value=(today - timedelta(days=7), today),
                           key="mon_custom")
    if not isinstance(picked, (tuple, list)) or len(picked) != 2:
        st.info("Pick a start and an end date.")
        st.stop()
    start = datetime.combine(picked[0], datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(picked[1] + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
else:
    span = {"Last 24 hours": timedelta(hours=24), "Last 7 days": timedelta(days=7),
            "Last 30 days": timedelta(days=30)}[preset]
    start, end = now - span, now
F = {"project_id": project_id, "start": start.isoformat(), "end": end.isoformat(),
     "provider": provider, "model": model}

tab_dash, tab_quality, tab_cost, tab_trace = st.tabs(
    ["Dashboard", "Quality and alerts", "Cost and pricing", "Feedback and traces"])


def fmt_ms(v):
    return f"{v:,.0f} ms" if v is not None else "n/a"


# ---------------- dashboard ----------------
with tab_dash:
    try:
        s = api.monitoring_summary(**F)
    except ApiError as err:
        show_api_error(err)
        st.stop()
    if s["empty"]:
        st.info("No requests were recorded in this range and filter. Run something in the "
                "Prompt Playground or an experiment, or widen the date range. "
                "Nothing is shown rather than showing made-up numbers.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Total requests", f"{s['total']:,}")
        b.metric("Succeeded", f"{s['success']:,}")
        c.metric("Failed", f"{s['failed']:,}")
        d.metric("Error rate", f"{s['error_rate']:.1%}")
        lat = s["latency"]
        e, f_, g, h = st.columns(4)
        e.metric("Avg latency", fmt_ms(lat["avg_ms"]))
        f_.metric("p50 latency", fmt_ms(lat["p50_ms"]))
        g.metric("p95 latency", fmt_ms(lat["p95_ms"]))
        h.metric("p99 latency", fmt_ms(lat["p99_ms"]))
        st.caption(f"Latency percentiles: {lat['method']}. Failed requests without a measured "
                   "latency are excluded from latency figures.")
        t = s["tokens"]
        i, j, k = st.columns(3)
        i.metric("Input tokens", f"{t['input']:,}")
        j.metric("Output tokens", f"{t['output']:,}")
        cost = s["cost"]
        if cost["totals_by_currency"]:
            total = ", ".join(f"{v:,.4f} {cur}" for cur, v in cost["totals_by_currency"].items())
            k.metric("Estimated cost", total, help=cost["note"])
        else:
            k.metric("Estimated cost", "unavailable", help="No matching prices configured. "
                     "See the Cost and pricing tab.")
        if t["requests_without_usage"]:
            st.caption(f"{t['requests_without_usage']} request(s) have no token counts (failed calls "
                       "or providers that did not report usage), so they are left out of token "
                       "and cost totals.")

        ts = api.monitoring_timeseries(**F)
        pts = ts["points"]
        st.markdown("#### Requests over time")
        df = pd.DataFrame(pts).set_index("bucket")
        st.bar_chart(df[["success", "failed"]], color=["#3FB27F", "#E5736F"])
        st.caption(f"Grouped by {ts['granularity']}. {ts['note']}")
        st.markdown("#### Latency trend (average per period)")
        lat_df = df[["avg_latency_ms"]].dropna()
        if len(lat_df):
            st.line_chart(lat_df, color=["#3FB27F"])
        else:
            st.info("No latency measurements in this range.")
        st.markdown("#### Token usage over time")
        st.bar_chart(df[["input_tokens", "output_tokens"]], color=["#4C8DD9", "#E7C45B"])

        bd = api.monitoring_breakdown(**F)
        st.markdown("#### Model comparison")
        st.dataframe(pd.DataFrame(bd["models"]), width="stretch", hide_index=True)
        st.markdown("#### Prompt-version comparison")
        if bd["prompt_versions"]:
            st.dataframe(pd.DataFrame(bd["prompt_versions"]).drop(columns=["prompt_id"]),
                         width="stretch", hide_index=True)
            st.caption("Only requests made through experiments carry a prompt version.")
        else:
            st.info("No requests with a prompt version in this range (they come from experiments).")
        il = s["input_length"]
        if il and il["n"]:
            st.markdown("#### Input length summary (characters)")
            st.dataframe(pd.DataFrame([{k: il[k] for k in ("n", "mean", "min", "p50", "p95", "max")}]),
                         width="stretch", hide_index=True)

# ---------------- quality and alerts ----------------
with tab_quality:
    try:
        al = api.monitoring_alerts(**F)
        q = api.monitoring_quality(**F)
        th = api.get_thresholds()
    except ApiError as err:
        show_api_error(err)
        st.stop()
    st.markdown("#### Alerts")
    if not al["alerts"]:
        st.success("No thresholds were exceeded in this range.")
    for a in al["alerts"]:
        box = st.warning if a["severity"] == "warning" else st.info
        box(f"**{a['title']}** — {a['message']}")
    st.caption(al["note"])

    st.markdown("#### Quality trend (from experiment evaluations)")
    if not q["series"]:
        st.info("No evaluation scores in this range. Run an experiment with metrics selected.")
    else:
        qdf = pd.DataFrame(q["series"])
        qdf["metric"] = qdf["metric"] + " (" + qdf["kind"].map(
            {"objective": "objective", "model_judgment": "model judgment"}) + ")"
        st.line_chart(qdf.pivot_table(index="bucket", columns="metric", values="mean_score"))
        st.caption(q["note"] + " Judge scores are on a 1-5 scale, other metrics on 0-1.")
        st.dataframe(pd.DataFrame(q["by_prompt_version"]).drop(columns=["prompt_id"]),
                     width="stretch", hide_index=True)

    with st.expander("Alert thresholds"):
        with st.form("thresholds"):
            x1, x2, x3 = st.columns(3)
            min_req = x1.number_input("Min requests before rate alerts", 1, 100000, th["min_requests"])
            err_max = x2.slider("Max error rate", 0.0, 1.0, float(th["error_rate_max"]), 0.01)
            lat_on = x3.checkbox("Alert on p95 latency", value=th["latency_p95_ms_max"] is not None)
            lat_max = x3.number_input("p95 limit (ms)", 1, 10_000_000,
                                      int(th["latency_p95_ms_max"] or 5000))
            y1, y2, y3 = st.columns(3)
            q_drop = y1.slider("Max quality drop (0-1)", 0.0, 1.0, float(th["quality_drop_max"]), 0.01)
            fmt_max = y2.slider("Max format-failure rate", 0.0, 1.0,
                                float(th["format_failure_rate_max"]), 0.01)
            samples = y3.number_input("Min scored samples", 1, 100000, th["min_samples"])
            z1, z2 = st.columns(2)
            fb_on = z1.checkbox("Alert on low ratings", value=th["feedback_avg_min"] is not None)
            fb_min = z1.slider("Min average rating", 1.0, 5.0, float(th["feedback_avg_min"] or 3.0), 0.1)
            len_chg = z2.slider("Input length change (relative)", 0.0, 5.0,
                                float(th["input_length_change_max"]), 0.05)
            if st.form_submit_button("Save thresholds", type="primary"):
                try:
                    api.save_thresholds({
                        "min_requests": int(min_req), "error_rate_max": err_max,
                        "latency_p95_ms_max": float(lat_max) if lat_on else None,
                        "quality_drop_max": q_drop, "format_failure_rate_max": fmt_max,
                        "feedback_avg_min": fb_min if fb_on else None,
                        "input_length_change_max": len_chg, "min_samples": int(samples)})
                    st.success("Thresholds saved.")
                except ApiError as err:
                    show_api_error(err)
    st.caption("Wording matters: a change in input statistics is a signal to look closer, not proof "
               "of harmful data drift, and quality problems should be backed by evaluation scores "
               "or user feedback.")

# ---------------- cost and pricing ----------------
with tab_cost:
    st.markdown("#### Estimated cost")
    try:
        sm = api.monitoring_summary(**F)
        prices = api.list_pricing()
    except ApiError as err:
        show_api_error(err)
        st.stop()
    cost = sm["cost"]
    if sm["empty"]:
        st.info("No requests in this range.")
    else:
        if cost["totals_by_currency"]:
            cols = st.columns(len(cost["totals_by_currency"]))
            for col, (cur, v) in zip(cols, cost["totals_by_currency"].items(), strict=True):
                col.metric(f"Total ({cur})", f"{v:,.4f}")
        st.markdown(pill("estimate", "plan") + (" " + pill("complete", "ok") if cost["complete"]
                    else " " + pill("incomplete: some requests unpriced", "bad")),
                    unsafe_allow_html=True)
        labels = {"estimated": "estimated", "partial": "partly priced", "no_pricing": "no price set",
                  "no_usage_data": "no token counts", "mixed_currency": "mixed currencies"}
        rows = [{**r, "status": labels.get(r["status"], r["status"])} for r in cost["by_model"]]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(cost["note"])

    st.markdown("#### Pricing configuration")
    st.warning("No prices are built in, because vendor prices change. Enter the price from your "
               "provider's own pricing page and note where you found it.")
    with st.form("add_price", clear_on_submit=True):
        p1, p2, p3 = st.columns(3)
        pv = p1.selectbox("Provider", [p["id"] for p in catalog["providers"]])
        pm = p2.text_input("Model ID (exact)", help="Must match the model ID used in requests.")
        eff = p3.date_input("Effective from", value=date.today())
        q1, q2, q3, q4 = st.columns(4)
        pin = q1.number_input("Input price", 0.0, 1_000_000.0, 0.0, format="%.4f")
        pout = q2.number_input("Output price", 0.0, 1_000_000.0, 0.0, format="%.4f")
        cur = q3.text_input("Currency", "USD", max_chars=3)
        unit = q4.selectbox("Unit", ["per_1M_tokens", "per_1K_tokens"])
        note = st.text_input("Source note (optional)", max_chars=300,
                             placeholder="e.g. provider pricing page, checked on 2026-10-11")
        if st.form_submit_button("Add price", type="primary", disabled=False):
            try:
                api.add_pricing({"provider": pv, "model": pm.strip(), "effective_from": eff.isoformat(),
                                 "input_price": pin, "output_price": pout, "currency": cur,
                                 "unit": unit, "source_note": note or None})
                st.success("Price added.")
                st.rerun()
            except ApiError as err:
                show_api_error(err)
    if prices:
        for p in prices:
            left, right = st.columns([6, 1])
            left.write(f"**{p['provider']} / {p['model']}** from {p['effective_from']}: "
                       f"{p['input_price']} in, {p['output_price']} out "
                       f"({p['currency']} {p['unit'].replace('_', ' ')})"
                       + (f" — _{p['source_note']}_" if p.get("source_note") else ""))
            if right.button("Delete", key=f"delp_{p['id']}"):
                try:
                    api.delete_pricing(p["id"])
                    st.rerun()
                except ApiError as err:
                    show_api_error(err)
    else:
        st.info("No prices configured yet.")

# ---------------- feedback and traces ----------------
with tab_trace:
    try:
        reqs = api.list_requests(limit=30, project_id=project_id)["items"]
        fbs = api.list_feedback(limit=20, **F)
    except ApiError as err:
        show_api_error(err)
        st.stop()
    st.markdown("#### Recent request traces")
    if not reqs:
        st.info("No traces yet.")
    else:
        st.dataframe(pd.DataFrame(reqs)[[
            "created_at", "status", "provider", "model", "prompt_version", "latency_ms",
            "input_tokens", "output_tokens", "retry_count", "error_category"]],
            width="stretch", hide_index=True)
        st.caption("Traces never contain API keys or authorization headers. Prompt and response "
                   "text is not stored unless enabled on the server (and is masked when it is).")
        labels = {f"{r['created_at'][:19]} · {r['model']} · {r['status']} · {r['request_id'][:8]}": r
                  for r in reqs}
        pick = labels[st.selectbox("Rate a request", list(labels))]
        from components.feedback import rate_response

        rate_response(pick["request_id"], f"mon_{pick['request_id']}")
    st.markdown("#### Recent feedback")
    if fbs:
        st.dataframe(pd.DataFrame(fbs)[["created_at", "rating", "comment", "provider", "model",
                                        "prompt_version", "request_id"]],
                     width="stretch", hide_index=True)
        fsum = sm["feedback"] if not sm["empty"] else None
        if fsum and fsum["count"]:
            st.caption(f"{fsum['count']} rating(s), average {fsum['avg_rating']}/5 in this range.")
    else:
        st.info("No feedback in this range.")
