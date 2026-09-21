import streamlit as st
import polars as pl
import sqlite3
from app.crud import students
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
    if st.button("🔎 Search People"):
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
                            results = students.find_students(search_term.strip())
                        st.session_state.search_results = results
    
    if st.button("Add Student"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Student'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a student row first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Student'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a student row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form


if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Student")
        st.markdown("*Required fields are marked with **`*`**")
        
        with st.form("add_student_form"):
            # Mandatory fields (highlighted with asterisk)
            first_name = st.text_input("First Name **`*`**")
            last_name = st.text_input("Last Name **`*`**")
            phone = st.text_input("Phone **`*`**")
            
            # Optional fields
            date_of_birth = st.date_input("Date of Birth", value=None, min_value=MIN_DATE, max_value=MAX_DATE)
            telegram_handle = st.text_input("Telegram Handle", value='@')
            address = st.text_area("Address")
            emergency_contact_phone = st.text_input("Emergency Contact Phone")
            emergency_contact_name = st.text_input("Emergency Contact Name")
            group_type = st.radio('Group Type', ['adult', 'child'], horizontal=True)
            comment = st.text_area("Comment")
            status = st.radio('Status', ['active', 'inactive'], horizontal=True)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Save Student", use_container_width=True)
            with col_btn2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.show_add_form = False
                    st.rerun()
            
            if submitted:
                if not first_name or not last_name or not phone:
                    st.error("First Name, Last Name, and Phone are required fields.")
                else:
                    try:
                        new_id = students.add_student(
                            first_name=first_name.strip(),
                            last_name=last_name.strip(),
                            phone=phone.strip(),
                            date_of_birth=date_of_birth,
                            telegram_handle=telegram_handle.strip() if telegram_handle else None,
                            address=address.strip() if address else None,
                            emergency_contact_phone=emergency_contact_phone.strip() if emergency_contact_phone else None,
                            emergency_contact_name=emergency_contact_name.strip() if emergency_contact_name else None,
                            group_type=group_type.strip() if group_type else None,
                            comment=comment.strip() if comment else None,
                            status=status.strip() if status else None
                        )
                        st.success(f"✅ Student added successfully! ID: {new_id}")
                        st.session_state.show_add_form = False
                        st.session_state.search_results = None
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")
    
# --- Display table with row selection ---
if st.session_state.search_results is None:
    df = load_table_data(DB_PATH, "students")
    st.markdown(f"**Total students:** {len(df):,}")
    event = st.dataframe(
    df,
    selection_mode="single-row",
    on_select="rerun",
    key="main_table"
)
# --- Capture selection ---
    if event and event.selection and event.selection.rows:
        row_idx = event.selection.rows[0]
        # Convert Polars row to dict (named=True gives a dict)
        st.session_state.selected_row_id = df.row(row_idx, named=True)
    else:
        st.session_state.selected_row_id = None
else:
    if len(st.session_state.search_results) > 0:
        # Convert results to Polars DataFrame
        results_df = pl.DataFrame(st.session_state.search_results, 
            schema=students.ALLOWED_STUDENT_FIELDS, 
            orient='row')
        event = st.dataframe(
            results_df,
            selection_mode="single-row",
            on_select="rerun",
            key="search_table"
        )
        # --- Capture selection ---
        if event and event.selection and event.selection.rows:
            row_idx = event.selection.rows[0]
            st.session_state.selected_row_id = results_df.row(row_idx, named=True)
        else:
            st.session_state.selected_row_id = None
    else:
        st.info("No matching records found.")
        event = None

# --- Edit Student Form ---
if st.session_state.show_edit_form:
    student_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No student selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        st.rerun()
    else:
        with st.container():
            st.write("### Edit Student")
            st.markdown("*Required fields are marked with **`*`**")
            
            with st.form("edit_student_form"):
                # Pre‑fill all fields
                first_name = st.text_input("First Name **`*`**", value=data.get('first_name', ''))
                last_name = st.text_input("Last Name **`*`**", value=data.get('last_name', ''))
                phone = st.text_input("Phone **`*`**", value=data.get('phone', ''))
                
                date_of_birth = st.date_input("Date of Birth", value=data.get('date_of_birth'), min_value=MIN_DATE, max_value=MAX_DATE)
                telegram_handle = st.text_input("Telegram Handle", value=data.get('telegram_handle', '@'))
                address = st.text_area("Address", value=data.get('address', ''))
                emergency_contact_phone = st.text_input("Emergency Contact Phone", value=data.get('emergency_contact_phone', ''))
                emergency_contact_name = st.text_input("Emergency Contact Name", value=data.get('emergency_contact_name', ''))
                
                # Radio for group_type – set index based on stored value
                group_options = ['adult', 'child']
                default_group_index = 0 if data.get('group_type') == 'adult' else 1
                group_type = st.radio('Group Type', group_options, horizontal=True, index=default_group_index)
                
                comment = st.text_area("Comment", value=data.get('comment', ''))
                
                # Radio for status
                status_options = ['active', 'inactive']
                default_status_index = 0 if data.get('status') == 'active' else 1
                status = st.radio('Status', status_options, horizontal=True, index=default_status_index)
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button("💾 Update Student", use_container_width=True)
                with col_btn2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.show_edit_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.edit_row_id = None
                        st.rerun()
                
                if submitted:
                    # Validate required fields
                    if not first_name or not last_name or not phone:
                        st.error("First Name, Last Name, and Phone are required fields.")
                    else:
                        try:
                            # Build update dict (all fields)
                            updates = {
                                'first_name': first_name.strip(),
                                'last_name': last_name.strip(),
                                'phone': phone.strip(),
                                'date_of_birth': date_of_birth,
                                'telegram_handle': telegram_handle.strip() if telegram_handle else None,
                                'address': address.strip() if address else None,
                                'emergency_contact_phone': emergency_contact_phone.strip() if emergency_contact_phone else None,
                                'emergency_contact_name': emergency_contact_name.strip() if emergency_contact_name else None,
                                'group_type': group_type.strip(),
                                'comment': comment.strip() if comment else None,
                                'status': status.strip()
                            }
                            # Call your update function
                            success = students.update_student(student_id, **updates)
                            if success:
                                st.success(f"✅ Student {student_id} updated successfully!")
                                # Clear edit state and refresh
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.session_state.search_results = None   # force refresh of table
                                st.rerun()
                        except ValueError as e:
                            st.error(f"Validation error: {e}")
                        except Exception as e:
                            st.error(f"Database error: {e}")

# --- Delete Student Form ---
if st.session_state.show_delete_form:
    student_id = st.session_state.selected_row_id['id']
    student_name = f"{st.session_state.selected_row_id.get('first_name', '')} {st.session_state.selected_row_id.get('last_name', '')}"
    
    with st.container():
        st.warning(f"⚠️ **Delete Student**")
        st.write(f"Are you sure you want to permanently delete **{student_name}** (ID: {student_id})?")
        st.write("This action **cannot be undone** and will remove all associated data.")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🗑️ Yes, Delete Permanently", use_container_width=True, type="primary"):
                try:
                    students.delete_student(student_id)
                    st.success(f"✅ Student {student_id} ({student_name}) deleted successfully!")
                    st.session_state.show_delete_form = False
                    st.session_state.selected_row_id = None
                    st.session_state.search_results = None  # Force refresh
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting student: {e}")
        
        with col_btn2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_delete_form = False
                st.rerun()