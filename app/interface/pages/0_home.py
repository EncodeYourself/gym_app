import streamlit as st

from app.interface.config import APP_NAME
from app.interface.ui.sidebar import render_grouped_sidebar
#from database.metadata import get_table_names
from app.interface.utils.logging import get_logger, setup_logging


st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
)

setup_logging()
logger = get_logger(__name__)



st.title(f"{APP_NAME}")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    ### Welcome

    Use the sidebar to navigate between sections:

    - **Students** — manage student records
    - **Plans** — view and edit membership plans
    - **Payments** — track income
    - **Attendance** — record training visits
    - **Finance** — expenses and cashflow
    """)

with col2:
    st.info("💡 Select a page from the sidebar to get started.")

