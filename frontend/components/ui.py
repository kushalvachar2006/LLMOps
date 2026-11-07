"""Small reusable UI pieces and the dark-green / charcoal look."""
import streamlit as st

from components.api_client import ApiError

_CSS = """
<style>
  .block-container { padding-top: 2rem; max-width: 1200px; }
  [data-testid="stMetric"] {
    background:#1E2522; border:1px solid #2B3530; border-radius:10px; padding:14px 16px;
  }
  .pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem;
          font-weight:600; border:1px solid transparent; }
  .pill-ok   { background:#12301F; color:#5BD39B; border-color:#1F5A3A; }
  .pill-bad  { background:#3A1A1A; color:#F08A8A; border-color:#6B2B2B; }
  .pill-plan { background:#232826; color:#9AA8A1; border-color:#33403A; }
  .muted { color:#9AA8A1; font-size:0.9rem; }
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def pill(text: str, kind: str = "plan") -> str:
    return f'<span class="pill pill-{kind}">{text}</span>'


def page_header(title: str, subtitle: str = "", badge: str = "") -> None:
    st.markdown(f"## {title} {badge}", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="muted">{subtitle}</p>', unsafe_allow_html=True)


def show_api_error(err: ApiError) -> None:
    st.error(err.message)
    if err.category == "unreachable":
        st.caption("Start the backend (see docs/setup.md), then reload this page.")
    elif err.category == "database_unavailable":
        st.caption("The API is running but MongoDB is unreachable. Check MONGODB_URI.")


def planned_page(title: str, phase: int, description: str) -> None:
    page_header(title, description, pill(f"Planned · Phase {phase}", "plan"))
    st.info(
        f"{title} is not implemented yet (scheduled for Phase {phase}). "
        "Nothing is shown here rather than showing fake data."
    )


def api_key_input(provider_id: str, provider_label: str, server_key: bool, key_id: str) -> str | None:
    """Password box for the user's own key. Held in this browser session's memory only."""
    store = st.session_state.setdefault("api_keys", {})
    value = st.text_input(
        f"{provider_label} API key (optional)" if server_key else f"{provider_label} API key",
        value=store.get(provider_id, ""),
        type="password",
        key=f"{key_id}_key_{provider_id}",
        help="Used only for your requests. It is sent to the backend in a request header, "
        "kept in memory for that one call, and never saved or shown again.",
    ).strip()
    store[provider_id] = value
    if not value:
        st.caption("Using the server's key." if server_key else "No server key is set: enter yours.")
    return value or None


def project_picker(key: str):
    """Select a project; returns the project dict or stops the page with a helpful message."""
    from components import api_client as api

    try:
        projects = api.list_projects()["items"]
    except ApiError as err:
        show_api_error(err)
        st.stop()
    if not projects:
        st.info("Create a project first on the Projects page.")
        st.stop()
    by_name = {p["name"]: p for p in projects}
    choice = st.selectbox("Project", list(by_name), key=key)
    return by_name[choice]
