import streamlit as st
import polars as pl
from app.database.database_ctl import get_connection
from app.crud.students import search_people


# Initialize session state
if 'show_search' not in st.session_state:
    st.session_state.show_search = False
if 'search_results' not in st.session_state:
    st.session_state.search_results = None

# Button to toggle search field
if st.button("🔍 Search People", use_container_width=True):
    st.session_state.show_search = not st.session_state.show_search
    st.session_state.search_results = None  # Clear previous results

# Show search field when button is clicked
if st.session_state.show_search:
    search_term = st.text_input("Enter name or ID:", key="search_input")
    
    if search_term:  # Only search when something is typed
        results = search_people(search_term)
        
        if results:
            df = pl.DataFrame(
                results,
                schema=["ID", "First Name", "Last Name"]
            )
            st.dataframe(df, use_container_width=True)
            st.success(f"Found {len(results)} result(s)")
        else:
            st.warning("No results found")

"""          
with col3:
    with st.popover("Actions", use_container_width=True) as popover:
        if st.button("➕ Add Student", use_container_width=True):
            st.session_state.show_add_form = True
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = False
            st.rerun()
        
        if st.button("✏️ Edit Student", use_container_width=True):
            st.session_state.show_edit_form = True
            st.session_state.show_add_form = False
            st.session_state.show_delete_form = False
            st.rerun()
        
        if st.button("🗑️ Delete Student", use_container_width=True):
            st.session_state.show_delete_form = True
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.rerun()
        if st.button('Close', use_container_width=True):
            st.session_state.show_delete_form = False
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.rerun()
"""