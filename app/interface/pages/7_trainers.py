import streamlit as st
import polars as pl
import sqlite3
from app.crud import trainers
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

if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Trainer")
        st.markdown("*Required fields are marked with **`*`**")

        with st.form("add_trainer_form"):
            # Mandatory fields (highlighted with asterisk)
            first_name = st.text_input("First Name **`*`**")
            last_name = st.text_input("Last Name **`*`**")
            phone = st.text_input("Phone **`*`**")

            # Optional fields
            telegram_handle = st.text_input("Telegram Handle", value='@')
            role = st.radio(
                'Role',
                ['coach', 'assistant', 'cutman', 'admin', 'other'],
                horizontal=True,
            )
            specialties = st.text_input(
                "Specialties", placeholder="youth, women, pads"
            )
            pay_type = st.selectbox(
                "Pay Type",
                ['volunteer', 'per_class', 'hourly', 'per_session', 'salary', 'other'],
                index=0,
            )
            pay_rate = st.number_input(
                "Pay Rate", min_value=0, step=100, value=0,
                help="Leave at 0 for volunteers.",
            )
            notes = st.text_area("Notes")
            status = st.radio('Status', ['active', 'inactive'], horizontal=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Save Trainer", use_container_width=True)
            with col_btn2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.show_add_form = False
                    st.rerun()

            if submitted:
                if not first_name or not last_name or not phone:
                    st.error("First Name, Last Name, and Phone are required fields.")
                else:
                    try:
                        new_id = trainers.add_trainer(
                            first_name=first_name.strip(),
                            last_name=last_name.strip(),
                            phone=phone.strip(),
                            telegram_handle=telegram_handle.strip() if telegram_handle else None,
                            role=role,
                            specialties=specialties.strip() if specialties else None,
                            pay_type=pay_type,
                            pay_rate=int(pay_rate) if pay_rate else None,
                            notes=notes.strip() if notes else None,
                            status=status,
                        )
                        st.success(
                            f"✅ Trainer added successfully! ID: {new_id}"
                        )
                        st.session_state.show_add_form = False
                        st.session_state.search_results = None
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")

if st.session_state.show_edit_form:
    trainer_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No trainer selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        logger.warning("Edit trainer form opened without selected trainer")
        st.rerun()
    else:
        with st.container():
            st.write("### Edit Trainer")
            st.markdown("*Required fields are marked with **`*`**")

            with st.form("edit_trainer_form"):
                # Pre-fill all fields
                first_name = st.text_input(
                    "First Name **`*`**",
                    value=data.get('first_name', ''),
                )

                last_name = st.text_input(
                    "Last Name **`*`**",
                    value=data.get('last_name', ''),
                )

                phone = st.text_input(
                    "Phone **`*`**",
                    value=data.get('phone', ''),
                )

                telegram_handle = st.text_input(
                    "Telegram Handle",
                    value=data.get('telegram_handle') or '',
                )

                # Role selectbox with stored value
                current_role = data.get('role', 'coach')
                default_role_index = (
                    list(trainers.VALID_ROLES).index(current_role)
                    if current_role in trainers.VALID_ROLES
                    else 0
                )
                role = st.selectbox(
                    "Role",
                    options=trainers.VALID_ROLES,
                    index=default_role_index,
                )

                specialties = st.text_input(
                    "Specialties",
                    value=data.get('specialties') or '',
                    placeholder="youth, women, pads",
                )

                # Pay type selectbox with stored value
                current_pay_type = data.get('pay_type') or 'volunteer'
                default_pay_type_index = (
                    list(trainers.VALID_PAY_TYPES).index(current_pay_type)
                    if current_pay_type in trainers.VALID_PAY_TYPES
                    else 0
                )
                pay_type = st.selectbox(
                    "Pay Type",
                    options=trainers.VALID_PAY_TYPES,
                    index=default_pay_type_index,
                )

                pay_rate = st.number_input(
                    "Pay Rate",
                    min_value=0,
                    step=100,
                    value=int(data.get('pay_rate') or 0),
                    help="Leave at 0 for volunteers.",
                )

                notes = st.text_area(
                    "Notes",
                    value=data.get('notes') or '',
                )

                # Status as radio (matches add form)
                current_status = data.get('status', 'active')
                default_status_index = (
                    list(trainers.VALID_STATUS).index(current_status)
                    if current_status in trainers.VALID_STATUS
                    else 0
                )
                status = st.radio(
                    "Status",
                    options=trainers.VALID_STATUS,
                    index=default_status_index,
                    horizontal=True,
                )

                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Trainer",
                        use_container_width=True,
                    )

                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel",
                        use_container_width=True,
                    ):
                        st.session_state.show_edit_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.edit_row_id = None
                        logger.info(
                            "Trainer edit cancelled: id=%s",
                            trainer_id,
                        )
                        st.rerun()

                if submitted:
                    # Validate required fields
                    if not first_name.strip():
                        st.error("First Name is required.")
                    elif not last_name.strip():
                        st.error("Last Name is required.")
                    elif not phone.strip():
                        st.error("Phone is required.")
                    else:
                        try:
                            updates = {
                                'first_name': first_name.strip(),
                                'last_name': last_name.strip(),
                                'phone': phone.strip(),
                                'telegram_handle': (
                                    telegram_handle.strip()
                                    if telegram_handle
                                    else None
                                ),
                                'role': role,
                                'specialties': (
                                    specialties.strip()
                                    if specialties else None
                                ),
                                'pay_type': pay_type,
                                'pay_rate': (
                                    int(pay_rate) if pay_rate else None
                                ),
                                'notes': (
                                    notes.strip()
                                    if notes else None
                                ),
                                'status': status,
                            }

                            success = trainers.update_trainer(
                                trainer_id,
                                **updates,
                            )

                            if success:
                                logger.info(
                                    "Trainer updated successfully: id=%s, "
                                    "first_name=%s, last_name=%s, role=%s",
                                    trainer_id,
                                    first_name.strip(),
                                    last_name.strip(),
                                    role,
                                )

                                st.success(
                                    f"✅ Trainer {trainer_id} updated "
                                    "successfully!"
                                )

                                # Clear edit state and refresh
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Trainer {trainer_id} not found. "
                                    "It may have been deleted."
                                )

                        except ValueError as e:
                            logger.warning(
                                "Validation failed for trainer update "
                                "id=%s: %s",
                                trainer_id,
                                e,
                            )
                            st.error(f"Validation error: {e}")

                        except Exception:
                            logger.exception(
                                "Database error while updating trainer "
                                "id=%s",
                                trainer_id,
                            )
                            st.error(
                                "An unexpected error occurred. "
                                "Check logs."
                            )

if st.session_state.search_results is None:
    df = load_table_data(DB_PATH, "trainers")

    event = st.dataframe(
        df,
        selection_mode="single-row",
        on_select="rerun",
        key="main_table"
    )
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


if st.session_state.show_delete_form:
    trainer_id = st.session_state.selected_row_id['id']
    trainer_name = f"{st.session_state.selected_row_id.get('first_name', '')} {st.session_state.selected_row_id.get('last_name', '')}"
    
    with st.container():
        st.warning(f"⚠️ **Delete class**")
        st.write(f"Are you sure you want to permanently delete **{trainer_name}** (ID: {trainer_id})?")
        st.write("This action **cannot be undone** and will remove all associated data.")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🗑️ Yes, Delete Permanently", use_container_width=True, type="primary"):
                try:
                    trainers.delete_trainer(trainer_id)
                    st.success(f"✅ trainer {trainer_id} ({trainer_name}) deleted successfully!")
                    st.session_state.show_delete_form = False
                    st.session_state.selected_row_id = None
                    st.session_state.search_results = None  # Force refresh
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting trainer: {e}")
        
        with col_btn2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_delete_form = False
                st.rerun()