"""Streamlit entry point: sidebar navigation only. Logic lives in the backend."""
import streamlit as st
from components.ui import apply_theme, planned_page

st.set_page_config(page_title="LLMOps Platform", page_icon="🟢", layout="wide")
apply_theme()


PLANNED: list[tuple[str, int, str]] = []  # every page is now implemented


def _planned_page(title: str, phase: int, text: str):
    def _page():
        planned_page(title, phase, text)

    return st.Page(_page, title=title, url_path=title.lower().replace(" ", "-"))


pages = [
    st.Page("pages/overview.py", title="Overview", url_path="overview", default=True),
    st.Page("pages/projects.py", title="Projects", url_path="projects"),
    st.Page("pages/playground.py", title="Prompt Playground", url_path="playground"),
    st.Page("pages/prompt_registry.py", title="Prompt Registry", url_path="registry"),
    st.Page("pages/datasets.py", title="Datasets", url_path="datasets"),
    st.Page("pages/experiments.py", title="Experiments", url_path="experiments"),
    st.Page("pages/evaluations.py", title="Evaluations", url_path="evaluations"),
    st.Page("pages/deployments.py", title="Deployments", url_path="deployments"),
    st.Page("pages/monitoring.py", title="Monitoring", url_path="monitoring"),
    *[_planned_page(*item) for item in PLANNED],
    st.Page("pages/settings.py", title="Settings", url_path="settings"),
]
st.sidebar.markdown("### LLMOps Platform")
st.navigation(pages).run()
