import datetime
import polars as pl
import streamlit as st
from app.interface.utils.logging import get_logger
import app.crud.payees as payees
import app.crud.expenses as expenses
from app.interface.config import DB_PATH
from app.interface.utils.functions import parse_time_str

logger = get_logger(__name__)

MIN_DATE = datetime.date(1970, 1, 1)
MAX_DATE = datetime.date.today()

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
    page_title="Expenses",
    layout="wide"
)

with st.sidebar:
    if st.button("🔎 Search Expense"):
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
                            results = expenses.find_expenses(search_term)
                            
                        st.session_state.search_results = results

    if st.button("Add Expense"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Expense'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select an expense first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Expense'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select an expense row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form

if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Expense")
        st.markdown("*Required fields are marked with **`*`**")

        # --- Load payees for the FK dropdown (OUTSIDE the form) ---
        # The payee selection drives the category prefill, so it has
        # to rerun when changed — forms don't rerun on inner changes.
        try:
            payees_list = payees.find_payees(is_active=1)
        except Exception as e:
            st.error(f"Could not load payees: {e}")
            payees_list = []

        if not payees_list:
            st.warning(
                "You need at least one active payee before adding an "
                "expense. Add a payee first."
            )
        else:
            payees_by_id = {p["id"]: p for p in payees_list}

            payee_id = st.selectbox(
                "Payee **`*`**",
                options=list(payees_by_id),
                format_func=lambda pid: payees_by_id[pid]["name"],
                help="Who received the money.",
                key="add_expense_payee",
            )

            selected_payee = payees_by_id[payee_id]

            # --- Category prefill from the payee's preferred_category ---
            category_options = [
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
            preferred = selected_payee.get('preferred_category')
            default_category = preferred if preferred in category_options else 'other'

            with st.form(f"add_expense_form_{payee_id}"):
                # --- Date ---
                expense_date = st.date_input(
                    "Expense Date **`*`**",
                    value=datetime.date.today(),
                    min_value=MIN_DATE,
                    max_value=MAX_DATE,
                )

                # --- Category ---
                # Key includes payee_id so switching payees resets the
                # default to the new payee's preferred category.
                category = st.selectbox(
                    "Category **`*`**",
                    options=category_options,
                    index=category_options.index(default_category),
                    key=f"add_expense_category_{payee_id}",
                )

                # --- Amount ---
                amount = st.number_input(
                    "Amount **`*`**",
                    min_value=0,
                    step=100,
                    value=0,
                )

                # --- Notes ---
                notes = st.text_area("Notes")

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Save Expense", use_container_width=True
                    )
                with col_btn2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.show_add_form = False
                        st.rerun()

                if submitted:
                    if amount <= 0:
                        st.error("Amount must be greater than zero.")
                    else:
                        try:
                            new_id = expenses.add_expense(
                                payee_id=payee_id,
                                expense_date=expense_date.isoformat(),
                                category=category,
                                amount=int(amount),
                                notes=notes.strip() or None,
                            )
                            st.success(f"✅ Expense added successfully! ID: {new_id}")
                            st.session_state.show_add_form = False
                            st.session_state.search_results = None
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Validation error: {e}")
                        except Exception as e:
                            st.error(f"Database error: {e}")


if st.session_state.show_edit_form:
    expense_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No expense selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        logger.warning("Edit expense form opened without selected expense")
        st.rerun()
    else:
        recurring_expense_id = data.get('recurring_expense_id')

        # --- Archived recurring instances are frozen ---
        # A row generated by a recurring definition is a historical record
        # of an accounting event. It is not editable. To change a future
        # instance, adjust the recurring definition itself; to correct
        # history, that's a different operation, not this form.
        if recurring_expense_id is not None:
            with st.container():
                st.write("### Expense (Archived)")
                st.info(
                    "This expense was generated from a recurring "
                    "definition and is a frozen historical record. "
                    "It cannot be edited or deleted."
                )
                st.caption(
                    f"Recurring definition id: `{recurring_expense_id}` · "
                    f"Payee: `{data.get('payee_name', '?')}` · "
                    f"Date: `{data.get('expense_date', '?')}` · "
                    f"Category: `{data.get('category', '?')}` · "
                    f"Amount: `{data.get('amount', '?')}`"
                )
                if st.button("❌ Close", use_container_width=True):
                    st.session_state.show_edit_form = False
                    st.session_state.selected_row_id = None
                    st.session_state.edit_row_id = None
                    st.rerun()
        else:
            # --- Load payees for the FK selectbox ---
            # All payees, not just active — the current one may have been
            # archived since the expense was recorded, and we still need
            # to display and select it.
            try:
                payees_list = payees.find_payees()
            except Exception as e:
                st.error(f"Could not load payees: {e}")
                payees_list = []

            payees_by_id = {p["id"]: p for p in payees_list}
            current_payee_id = data.get('payee_id')

            with st.container():
                st.write("### Edit Expense")
                st.markdown("*Required fields are marked with **`*`**")

                with st.form(f"edit_expense_form_{expense_id}"):
                    # --- Payee selectbox ---
                    if payees_by_id:
                        payee_options = list(payees_by_id.keys())
                        if current_payee_id not in payee_options:
                            st.warning(
                                f"Original payee (id={current_payee_id}) "
                                "no longer exists. Please pick another."
                            )
                            default_payee_index = 0
                        else:
                            default_payee_index = payee_options.index(
                                current_payee_id
                            )

                        def _payee_label(pid: int) -> str:
                            p = payees_by_id[pid]
                            suffix = (
                                "" if p.get("is_active", 1)
                                else "  (inactive)"
                            )
                            return f'{p["name"]}{suffix}'

                        payee_id = st.selectbox(
                            "Payee **`*`**",
                            options=payee_options,
                            index=default_payee_index,
                            format_func=_payee_label,
                        )
                    else:
                        st.warning("No payees available.")
                        payee_id = None

                    # --- Date ---
                    raw_date = data.get('expense_date') or datetime.date.today().isoformat()
                    try:
                        default_expense_date = datetime.date.fromisoformat(raw_date[:10])
                    except ValueError:
                        default_expense_date = datetime.date.today()

                    expense_date = st.date_input(
                        "Expense Date **`*`**",
                        value=default_expense_date,
                        min_value=MIN_DATE,
                        max_value=MAX_DATE,
                    )

                    # --- Category ---
                    category_options = [
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
                    current_category = data.get('category', 'other')
                    default_category_index = (
                        category_options.index(current_category)
                        if current_category in category_options
                        else 0
                    )
                    category = st.selectbox(
                        "Category **`*`**",
                        options=category_options,
                        index=default_category_index,
                    )

                    # --- Amount ---
                    amount = st.number_input(
                        "Amount **`*`**",
                        min_value=0,
                        step=100,
                        value=int(data.get('amount') or 0),
                    )

                    # --- Notes ---
                    notes = st.text_area(
                        "Notes",
                        value=data.get('notes') or '',
                    )

                    # --- Buttons ---
                    col_btn1, col_btn2 = st.columns(2)

                    with col_btn1:
                        submitted = st.form_submit_button(
                            "💾 Update Expense",
                            use_container_width=True,
                        )

                    with col_btn2:
                        if st.form_submit_button(
                            "❌ Cancel",
                            use_container_width=True,
                        ):
                            st.session_state.show_edit_form = False
                            #st.session_state.selected_row_id = None
                            #st.session_state.edit_row_id = None
                            logger.info(
                                "Expense edit cancelled: id=%s", expense_id
                            )
                            st.rerun()

                    if submitted:
                        if payee_id is None:
                            st.error("Payee is required.")
                        else:
                            try:
                                updates = {
                                    'payee_id': payee_id,
                                    'expense_date': expense_date.isoformat(),
                                    'category': category,
                                    'amount': int(amount),
                                    'notes': notes.strip() or None,
                                }

                                success = expenses.update_expense(
                                    expense_id, **updates
                                )

                                if success:
                                    logger.info(
                                        "Expense updated successfully: id=%s, "
                                        "payee_id=%s, category=%s, amount=%s",
                                        expense_id,
                                        payee_id,
                                        category,
                                        amount,
                                    )
                                    st.success(
                                        f"✅ Expense {expense_id} updated "
                                        f"successfully!"
                                    )
                                    st.session_state.show_edit_form = False
                                    st.session_state.selected_row_id = None
                                    st.session_state.edit_row_id = None
                                    st.session_state.search_results = None
                                    st.rerun()
                                else:
                                    st.warning(
                                        f"Expense {expense_id} not found. "
                                        "It may have been deleted."
                                    )

                            except ValueError as e:
                                logger.warning(
                                    "Validation failed for expense update "
                                    "id=%s: %s",
                                    expense_id,
                                    e,
                                )
                                st.error(f"Validation error: {e}")

                            except Exception:
                                logger.exception(
                                    "Database error while updating expense "
                                    "id=%s",
                                    expense_id,
                                )
                                st.error(
                                    "An unexpected error occurred. "
                                    "Check logs."
                                )
        
# --- Display table with row selection ---
active_df = None
event = None

if st.session_state.search_results is None:
    rows = expenses.find_expenses()
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
            schema=expenses.ALLOWED_EXPENSES_FIELDS,
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


# --- Capture selection (bounds-checked) ---
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
        # Streamlit kept a selection from a previous, larger dataframe.
        logger.warning(
            "Stale row selection: index=%s, height=%s — clearing",
            row_idx,
            active_df.height,
        )
        #st.session_state.selected_row_id = None
else:
    #st.session_state.selected_row_id = None
    pass

# --- Delete Expense Form ---
if st.session_state.show_delete_form:
    data = st.session_state.selected_row_id

    if data is None:
        st.error("No expense selected. Please close and select a row.")
        st.session_state.show_delete_form = False
        st.rerun()
    else:
        expense_id = data.get('id')
        payee_name = data.get('payee_name', '?')
        expense_date = data.get('expense_date', '?')
        category = data.get('category', '?')
        amount = data.get('amount', '?')
        recurring_expense_id = data.get('recurring_expense_id')

        with st.container():
            st.warning("⚠️ **Delete Expense**")

            # --- Frozen branch: recurring instances cannot be deleted ---
            if recurring_expense_id is not None:
                st.write(
                    f"The expense to **{payee_name}** on **{expense_date}** "
                    f"was generated from a recurring definition and is a "
                    f"frozen historical record."
                )
                st.info(
                    f"This expense is part of a recurring series "
                    f"(definition id=`{recurring_expense_id}`) and cannot "
                    f"be deleted or edited. To stop future instances, "
                    f"deactivate the recurring definition itself."
                )
                st.caption(
                    f"Category: `{category}` · Amount: `{amount}`"
                )
                if st.button("❌ Close", use_container_width=True):
                    st.session_state.show_delete_form = False
                    st.rerun()

            # --- Editable branch: manual expense ---
            else:
                st.write(
                    f"Are you sure you want to permanently delete the "
                    f"**{category}** expense to **{payee_name}** on "
                    f"**{expense_date}** for **{amount}**?"
                )
                st.write("This action **cannot be undone**.")
                st.caption(
                    "For accounting accuracy, prefer correcting the row "
                    "via the edit form over deleting it. Delete is only "
                    "for entries that never should have existed."
                )

                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button(
                        "🗑️ Yes, Delete",
                        use_container_width=True,
                        type="primary",
                    ):
                        try:
                            if expenses.delete_expense(expense_id):
                                st.success(
                                    "✅ Expense deleted successfully!"
                                )
                                st.session_state.show_delete_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    "That expense no longer exists. It may "
                                    "have been deleted in another session."
                                )
                                st.session_state.show_delete_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting expense: {e}")

                with col_btn2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_delete_form = False
                        st.rerun()