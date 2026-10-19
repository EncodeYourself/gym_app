import datetime
import polars as pl
import streamlit as st
from app.interface.utils.logging import get_logger
import app.crud.payees as payees
import app.crud.trainers as trainers
from app.interface.config import DB_PATH
from app.interface.utils.functions import parse_time_str
import sqlite3
logger = get_logger(__name__)


defaults = {
    "show_search" : False,
    "show_add_form": False,
    "show_edit_form": False,
    "show_delete_form": False,
    "selected_row_id": None,
    "edit_row_id": None,
    "search_results": None,
}


for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.set_page_config(
    page_title="Payees",
    layout="wide"
)

with st.sidebar:
    if st.button("🔎 Search Payee"):
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
                            results = payees.find_payees(search_term)
                            
                        st.session_state.search_results = results

    if st.button("Add Payee"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Payee'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a payee first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Payee'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a payee row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form

# --- Add Payee Form ---
if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Payee")
        st.markdown("*Required fields are marked with **`*`**")

        # --- Trainer link decision (OUTSIDE form: drives name prefill below) ---
        is_trainer = st.checkbox(
            "This payee is a trainer",
            value=False,
            help=(
                "Trainers and external vendors share the same payee table. "
                "Check this if the person receiving money is one of your "
                "coaches. Only one payee per trainer is allowed."
            ),
        )

        linked_trainer_id = None
        linked_trainer_label = None

        if is_trainer:
            try:
                trainers_list = trainers.find_trainers(status='active')
            except Exception as e:
                st.error(f"Could not load trainers: {e}")
                trainers_list = []

            if not trainers_list:
                st.warning(
                    "No active trainers found. Deactivate this checkbox or "
                    "add a trainer first."
                )
            else:
                trainers_by_id = {t["id"]: t for t in trainers_list}
                linked_trainer_id = st.selectbox(
                    "Trainer **`*`**",
                    options=list(trainers_by_id),
                    format_func=lambda tid: (
                        f'{trainers_by_id[tid]["last_name"]} '
                        f'{trainers_by_id[tid]["first_name"]} '
                        f'(ID {tid})'
                    ),
                )
                linked_trainer_label = (
                    f'{trainers_by_id[linked_trainer_id]["first_name"]} '
                    f'{trainers_by_id[linked_trainer_id]["last_name"]}'
                )

        # --- Name prefill from the selected trainer ---
        default_name = linked_trainer_label or ""

        with st.form(f"add_payee_form_{linked_trainer_id or 'external'}"):
            # --- Name ---
            # Key includes the trainer id so switching trainers resets
            # the field to the new prefill instead of keeping the old value.
            name = st.text_input(
                "Payee Name **`*`**",
                value=default_name,
                key=f"payee_name_{linked_trainer_id or 'external'}",
                help="Name as it should appear on expense records.",
            )

            # --- Preferred category ---
            category_options = [
                '—',
                'rent',
                'utilities',
                'cleaning',
                'salary',
                'equipment',
                'repairs',
                'marketing',
                'taxes',
                'other',
            ]
            category_choice = st.selectbox(
                "Preferred Category",
                options=category_options,
                index=category_options.index('salary') if is_trainer else 0,
                help=(
                    "Used to pre-fill the category field when this payee "
                    "is selected on a new expense. Leave as — for no default."
                ),
            )

            # --- Active status ---
            is_active = st.checkbox("Active", value=True)

            # --- Notes ---
            notes = st.text_area("Notes")

            # --- Buttons ---
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button(
                    "💾 Save Payee", use_container_width=True
                )
            with col_btn2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.show_add_form = False
                    st.rerun()

            if submitted:
                # --- Validate ---
                if not name.strip():
                    st.error("Payee Name is required.")
                elif is_trainer and linked_trainer_id is None:
                    st.error("Please select a trainer.")
                else:
                    try:
                        new_id = payees.add_payee(
                            name=name.strip(),
                            linked_trainer_id=linked_trainer_id,
                            preferred_category=(
                                None if category_choice == '—' else category_choice
                            ),
                            is_active=1 if is_active else 0,
                            notes=notes.strip() or None,
                        )
                        st.success(f"✅ Payee '{name.strip()}' added successfully!")
                        st.session_state.show_add_form = False
                        st.session_state.search_results = None
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")

# --- Edit Payee Form ---
if st.session_state.show_edit_form:
    payee_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No payee selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        logger.warning("Edit payee form opened without selected payee")
        st.rerun()
    else:
        current_linked_trainer_id = data.get('linked_trainer_id')
        currently_linked = current_linked_trainer_id is not None
        expense_count = data.get('expense_count', 0)

        with st.container():
            st.write("### Edit Payee")
            st.markdown("*Required fields are marked with **`*`**")

            # --- Context caption ---
            if expense_count > 0:
                st.caption(
                    f"This payee has **{expense_count}** recorded "
                    f"expense{'s' if expense_count != 1 else ''}. "
                    f"The name and category can be edited; existing "
                    f"expenses keep their own copy of the amount and date."
                )

            # --- Trainer link checkbox (OUTSIDE form: drives which
            #     widgets render inside) ---
            is_trainer = st.checkbox(
                "This payee is a trainer",
                value=currently_linked,
                key=f"edit_payee_is_trainer_{payee_id}",
                help=(
                    "Trainers and external vendors share the same payee "
                    "table. Unlinking a trainer does not delete the "
                    "trainer — it only removes the payee-to-trainer "
                    "reference."
                ),
            )

            linked_trainer_id = None

            if is_trainer:
                try:
                    trainers_list = trainers.find_trainers()  # all, not just active
                except Exception as e:
                    st.error(f"Could not load trainers: {e}")
                    trainers_list = []

                if not trainers_list:
                    st.warning(
                        "No trainers found. Uncheck the box or add a "
                        "trainer first."
                    )
                else:
                    trainers_by_id = {t["id"]: t for t in trainers_list}

                    if current_linked_trainer_id in trainers_by_id:
                        default_index = list(trainers_by_id).index(
                            current_linked_trainer_id
                        )
                    else:
                        # Either linking for the first time (was external),
                        # or the current link points at a trainer that's
                        # no longer in the list.
                        default_index = 0
                        if current_linked_trainer_id is not None:
                            st.warning(
                                f"Currently linked to trainer "
                                f"{current_linked_trainer_id}, which is "
                                f"not in the list. Please pick a trainer."
                            )

                    def _trainer_label(tid: int) -> str:
                        t = trainers_by_id[tid]
                        suffix = "" if t.get("status") == "active" else "  (inactive)"
                        return (
                            f'{t["last_name"]} {t["first_name"]} '
                            f'(ID {tid}){suffix}'
                        )

                    linked_trainer_id = st.selectbox(
                        "Trainer **`*`**",
                        options=list(trainers_by_id),
                        index=default_index,
                        format_func=_trainer_label,
                        key=f"edit_payee_trainer_{payee_id}",
                    )

            # --- Main form ---
            with st.form(f"edit_payee_form_{payee_id}"):
                # --- Name ---
                name = st.text_input(
                    "Payee Name **`*`**",
                    value=data.get('name', ''),
                    key=f"edit_payee_name_{payee_id}",
                    help="Name as it appears on expense records.",
                )

                # --- Preferred category ---
                category_options = [
                    '—',
                    'rent',
                    'utilities',
                    'cleaning',
                    'salary',
                    'equipment',
                    'repairs',
                    'marketing',
                    'taxes',
                    'other',
                ]
                current_category = data.get('preferred_category')
                default_category_index = (
                    category_options.index(current_category)
                    if current_category in category_options
                    else 0
                )
                category_choice = st.selectbox(
                    "Preferred Category",
                    options=category_options,
                    index=default_category_index,
                    key=f"edit_payee_category_{payee_id}",
                    help=(
                        "Used to pre-fill the category field when this "
                        "payee is selected on a new expense."
                    ),
                )

                # --- Active status ---
                is_active = st.checkbox(
                    "Active",
                    value=bool(data.get('is_active', 1)),
                    key=f"edit_payee_active_{payee_id}",
                )

                # --- Notes ---
                notes = st.text_area(
                    "Notes",
                    value=data.get('notes') or '',
                    key=f"edit_payee_notes_{payee_id}",
                )

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Payee",
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
                        logger.info("Payee edit cancelled: id=%s", payee_id)
                        st.rerun()

                if submitted:
                    # --- Validate ---
                    if not name.strip():
                        st.error("Payee Name is required.")
                    elif is_trainer and linked_trainer_id is None:
                        st.error("Please select a trainer.")
                    else:
                        try:
                            updates = {
                                'name': name.strip(),
                                'linked_trainer_id': (
                                    linked_trainer_id if is_trainer else None
                                ),
                                'preferred_category': (
                                    None
                                    if category_choice == '—'
                                    else category_choice
                                ),
                                'is_active': 1 if is_active else 0,
                                'notes': notes.strip() or None,
                            }

                            success = payees.update_payee(payee_id, **updates)

                            if success:
                                logger.info(
                                    "Payee updated successfully: id=%s, "
                                    "name=%s",
                                    payee_id,
                                    name.strip(),
                                )
                                st.success(
                                    f"✅ Payee '{name.strip()}' updated "
                                    f"successfully!"
                                )
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Payee {payee_id} not found. "
                                    "It may have been deleted."
                                )

                        except ValueError as e:
                            logger.warning(
                                "Validation failed for payee update "
                                "id=%s: %s",
                                payee_id,
                                e,
                            )
                            st.error(f"Validation error: {e}")

                        except Exception:
                            logger.exception(
                                "Database error while updating payee id=%s",
                                payee_id,
                            )
                            st.error(
                                "An unexpected error occurred. Check logs."
                            )


# --- Display table with row selection ---
active_df = None
event = None

if st.session_state.search_results is None:
    rows = payees.find_payees()
    active_df = pl.DataFrame(rows) if rows else pl.DataFrame()

    event = st.dataframe(
        active_df,
        selection_mode="single-row",
        on_select="rerun",
        key="main_table",
    )
else:
    if len(st.session_state.search_results) > 0:
        active_df = pl.DataFrame(
            st.session_state.search_results,
            schema=payees.ALLOWED_PAYEE_FIELDS,
            orient="row",
        )
        event = st.dataframe(
            active_df,
            selection_mode="single-row",
            on_select="rerun",
            key="search_table",
        )
    else:
        st.info("No matching records found.")
if (
    event
    and event.selection
    and event.selection.rows
    and active_df is not None
):
    row_idx = event.selection.rows[0]
    if 0 <= row_idx < active_df.height:
        st.session_state.selected_row_id = active_df.row(row_idx, named=True)
    else:
        logger.warning(
            "Stale row selection: index=%s, height=%s — clearing",
            row_idx,
            active_df.height,
        )
        st.session_state.selected_row_id = None
else:
    st.session_state.selected_row_id = None
    
# --- Delete Payee Form ---
if st.session_state.show_delete_form:
    data = st.session_state.selected_row_id

    if data is None:
        st.error("No payee selected. Please close and select a row.")
        st.session_state.show_delete_form = False
        st.rerun()
    else:
        payee_id = data.get('id')
        payee_name = data.get('name', '?')
        preferred_category = data.get('preferred_category')
        is_active = bool(data.get('is_active', 1))
        linked_trainer_id = data.get('linked_trainer_id')
        trainer_first = data.get('trainer_first_name')
        trainer_last = data.get('trainer_last_name')
        expense_count = data.get('expense_count', 0)

        with st.container():
            st.warning("⚠️ **Delete Payee**")
            st.write(f"Are you sure you want to delete **{payee_name}**?")
            st.caption(
                f"Category: `{preferred_category or '—'}` · "
                f"Status: `{'active' if is_active else 'inactive'}`"
                + (
                    f" · Linked trainer: {trainer_first or ''} {trainer_last or ''}".rstrip()
                    if linked_trainer_id else ""
                )
            )

            # --- Branch on whether the payee has history ---
            if expense_count > 0:
                st.error(
                    f"This payee has **{expense_count}** recorded "
                    f"expense{'s' if expense_count != 1 else ''} and cannot "
                    f"be deleted. **Deactivate it instead** (edit → "
                    f"is_active = off) to hide it from new expenses while "
                    f"preserving the historical record."
                )

                if st.button("❌ Close", use_container_width=True):
                    st.session_state.show_delete_form = False
                    st.rerun()

            else:
                st.write("This action **cannot be undone**.")

                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button(
                        "🗑️ Yes, Delete",
                        use_container_width=True,
                        type="primary",
                    ):
                        try:
                            if payees.delete_payee(payee_id):
                                st.success("✅ Payee deleted successfully!")
                                st.session_state.show_delete_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    "That payee no longer exists. It may "
                                    "have been deleted in another session."
                                )
                                st.session_state.show_delete_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                        except ValueError as e:
                            # Shouldn't fire when expense_count == 0,
                            # but if it does, it's a race — another
                            # session added an expense between page
                            # load and button click.
                            st.error(f"Cannot delete payee: {e}")
                        except Exception as e:
                            st.error(f"Error deleting payee: {e}")

                with col_btn2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_delete_form = False
                        st.rerun()
