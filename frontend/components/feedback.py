"""Small rating widget: stars plus an optional comment, tied to one request ID."""
import streamlit as st

from components import api_client as api
from components.api_client import ApiError
from components.ui import show_api_error


def rate_response(request_id: str, key: str) -> None:
    with st.expander("Rate this response"):
        rating = st.radio("Rating", [1, 2, 3, 4, 5], index=None, horizontal=True,
                          format_func=lambda n: "★" * n, key=f"{key}_rating")
        comment = st.text_input("Comment (optional)", max_chars=1000, key=f"{key}_comment",
                                help="Emails, phone numbers and key-like text are masked before saving.")
        if st.button("Send feedback", key=f"{key}_send", disabled=rating is None):
            try:
                api.add_feedback({"request_id": request_id, "rating": rating,
                                  "comment": comment or None})
                st.success("Thanks, your feedback was saved.")
            except ApiError as err:
                show_api_error(err)
