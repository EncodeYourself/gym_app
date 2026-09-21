import streamlit as st
import polars as pl
import sqlite3
from app.crud import substitutions
import datetime
from app.interface.utils.logging import get_logger

logger = get_logger(__name__)

defaults = {
    "show_search": False,
    "search_results": None,
    "show_add_form": False,
    "show_edit_form": False,
    "show_delete_form": False,
    "selected_row_id": None,
    "edit_row_id": None,
}

MIN_DATE = datetime.date(1970, 1, 1)
MAX_DATE = datetime.date.today()

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


st.set_page_config(
    page_title="Students Table",
    page_icon="👨‍🎓",
    layout="wide"
)
# Hardcoded database path
DB_PATH = "app/data/business.db"

# Helper function to load data
def load_table_data(db_path, table_name):
    conn = sqlite3.connect(db_path)
    query = f'SELECT * FROM {table_name}'
    df = pl.read_database(query, conn)
    conn.close()
    return df

with st.sidebar:
    if st.button("🔎 Search Trainer"):
        st.session_state.show_search = not st.session_state.show_search
        
        if not st.session_state.show_search:
            st.session_state.search_results = None

    if st.session_state.show_search:
        with st.container():
            st.write("### Enter search term")
            with st.form("search_form"):   # <-- new form wrapper
                search_term = st.text_input(
                    "Search by ID (exact) or name (partial)",
                    key="search_input"
                )
                # Submit button inside the form (use form_submit_button)
                submitted = st.form_submit_button("Execute Search")
                
                if submitted:
                    if search_term.strip() == "":
                        st.warning("Please enter a search term.")
                    else:
                        with st.spinner("Searching..."):
                            results = trainers.search_trainers(search_term.strip())
                        st.session_state.search_results = results
    
    if st.button("Add Trainer"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Trainer'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a student row first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Trainer'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a student row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form