import streamlit as st
from components import api_client as api
from components.api_client import ApiError
from components.ui import page_header, show_api_error

page_header("Projects", "Group prompts, datasets and deployments under a project.")

with st.expander("Create a project", expanded=False):
    with st.form("create_project", clear_on_submit=True):
        name = st.text_input("Name", max_chars=100)
        desc = st.text_area("Description", max_chars=500)
        if st.form_submit_button("Create", type="primary"):
            try:
                api.create_project(name, desc)
                st.success("Project created.")
            except ApiError as err:
                show_api_error(err)

try:
    data = api.list_projects()
except ApiError as err:
    show_api_error(err)
    st.stop()

if not data["items"]:
    st.info("No projects yet. Create your first project above.")
    st.stop()

st.caption(f"{data['total']} project(s)")
for p in data["items"]:
    with st.container(border=True):
        st.markdown(f"**{p['name']}**")
        st.markdown(f'<p class="muted">{p["description"] or "No description"}</p>',
                    unsafe_allow_html=True)
        st.caption(f"ID {p['id']} · created {p['created_at'][:19]} UTC")
        with st.expander("Edit / delete"):
            new_name = st.text_input("Name", p["name"], key=f"n_{p['id']}")
            new_desc = st.text_area("Description", p["description"], key=f"d_{p['id']}")
            left, right = st.columns(2)
            if left.button("Save changes", key=f"s_{p['id']}"):
                try:
                    api.update_project(p["id"], name=new_name, description=new_desc)
                    st.rerun()
                except ApiError as err:
                    show_api_error(err)
            confirm = right.checkbox("Confirm delete", key=f"c_{p['id']}")
            if right.button("Delete project", key=f"x_{p['id']}", disabled=not confirm):
                try:
                    api.delete_project(p["id"])
                    st.rerun()
                except ApiError as err:
                    show_api_error(err)
