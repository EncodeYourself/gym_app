from app.database.database_ctl import get_connection
import app.crud.students as students
import app.crud.payments as payments
import app.crud.plans as plans
from app.interface.config import DB_PATH
import datetime
import polars as pl
import streamlit as st
import sqlite3
from app.interface.utils.logging import get_logger

logger  = get_logger(__name__)

def load_table_data(db_path, table_name):
    conn = sqlite3.connect(db_path)
    query = f'SELECT * FROM {table_name}'
    df = pl.read_database(query, conn)
    conn.close()
    return df

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
    page_title="Payments",
    page_icon="👨‍🎓",
    layout="wide"
)


for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.set_page_config(
    page_title="Payments Table",
    page_icon="👨‍🎓",
    layout="wide"
)


with st.sidebar:
    if st.button("🔎 Search Payment"):
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
                            results = payments.search_payments(search_term)
                            
                        st.session_state.search_results = results

    if st.button("Add Payment"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Payment'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a class first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Payment'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a class row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form

if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Payment")
        st.markdown("*Required fields are marked with **`*`**")

        # Reference data for the FK dropdowns (loaded once, outside the form)
        try:
            students_list = students.find_students()   # adapt to your API
            plans_list = plans.find_plans(is_active=1)            # adapt to your API
        except Exception as e:
            st.error(f"Could not load reference data: {e}")
            students_list, plans_list = [], []

        if not students_list or not plans_list:
            st.warning(
                "You need at least one student and one plan before adding a payment."
            )
        else:
            students_by_id = {s["id"]: s for s in students_list}
            plans_by_id = {p["id"]: p for p in plans_list}

            with st.form("add_payment_form"):
                # --- Required fields ---
                student_id = st.selectbox(
                    "Student **`*`**",
                    options=list(students_by_id),
                    format_func=lambda sid: (
                        f'{students_by_id[sid]["last_name"]} '
                        f'{students_by_id[sid]["first_name"]} (ID {sid})'
                    ),
                )
                plan_id = st.selectbox(
                    "Plan **`*`**",
                    options=list(plans_by_id),
                    format_func=lambda pid: (
                        f'{plans_by_id[pid]["name"]} — {plans_by_id[pid]["price"]}'
                    ),
                )
                amount_paid = st.number_input(
                    "Amount Paid **`*`**", min_value=0, step=1, value=0
                )
                method = st.radio(
                    "Method **`*`**",
                    ["cash", "card", "bank_transfer", "other"],
                    horizontal=True,
                )

                # --- Optional fields ---
                payment_date = st.date_input(
                    "Payment Date",
                    value=datetime.date.today(),
                    min_value=MIN_DATE,
                    max_value=MAX_DATE,
                )
                receipt_number = st.text_input("Receipt Number")
                notes = st.text_area("Notes")
                status = st.radio(
                    "Status", ["paid", "refunded", "voided"], horizontal=True
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Save Payment", use_container_width=True
                    )
                with col_btn2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.show_add_form = False
                        st.rerun()

                if submitted:
                    try:
                        new_id = payments.add_payment(
                            student_id=student_id,
                            plan_id=plan_id,
                            amount_paid=int(amount_paid),
                            method=method,
                            payment_date=payment_date.isoformat(),
                            receipt_number=receipt_number.strip() or None,
                            notes=notes.strip() or None,
                            status=status,
                        )
                        st.success(f"✅ Payment added successfully! ID: {new_id}")
                        st.session_state.show_add_form = False
                        st.session_state.payment_search_results = None
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")

# --- Edit Payment Form ---
if st.session_state.show_edit_form:
    payment_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No payment selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        logger.warning("Edit payment form opened without selected payment")
        st.rerun()
    else:
        # --- Load students for the FK selectbox ---
        try:
            students_list = students.find_students()
        except Exception as e:
            st.error(f"Could not load students: {e}")
            students_list = []

        students_by_id = {s["id"]: s for s in students_list}
        current_student_id = data.get('student_id')

        with st.container():
            st.write("### Edit Payment")
            st.markdown("*Required fields are marked with **`*`**")

            with st.form(f"edit_payment_form_{payment_id}"):
                # --- Student selectbox ---
                if students_by_id:
                    student_options = list(students_by_id.keys())
                    if current_student_id not in student_options:
                        st.warning(
                            f"Original student (id={current_student_id}) "
                            "no longer exists. Please pick another."
                        )
                        default_student_index = 0
                    else:
                        default_student_index = student_options.index(
                            current_student_id
                        )

                    selected_student_id = st.selectbox(
                        "Student **`*`**",
                        options=student_options,
                        index=default_student_index,
                        format_func=lambda sid: (
                            f'{students_by_id[sid]["last_name"]} '
                            f'{students_by_id[sid]["first_name"]} '
                            f'({students_by_id[sid].get("phone") or "no phone"})'
                        ),
                        help="Type to search by last name, first name, or phone.",
                    )
                else:
                    st.warning("No students available.")
                    selected_student_id = None

                # --- Amount ---
                amount_paid = st.number_input(
                    "Amount Paid **`*`**",
                    min_value=0,
                    step=100,
                    value=int(data.get('amount_paid') or 0),
                )

                # --- Category ---
                category_options = [
                    'membership_new',
                    'membership_renewal',
                    'membership_upgrade',
                    'drop_in',
                    'credit_payment',
                    'refund',
                    'other',
                ]
                current_category = data.get('payment_category', 'membership_new')
                default_category_index = (
                    category_options.index(current_category)
                    if current_category in category_options
                    else 0
                )
                payment_category = st.selectbox(
                    "Category **`*`**",
                    options=category_options,
                    index=default_category_index,
                )

                # --- Method ---
                method_options = ['cash', 'card', 'bank_transfer', 'other']
                current_method = data.get('method', 'cash')
                default_method_index = (
                    method_options.index(current_method)
                    if current_method in method_options
                    else 0
                )
                method = st.radio(
                    "Method **`*`**",
                    options=method_options,
                    index=default_method_index,
                    horizontal=True,
                )

                # --- Date ---
                # Stored as 'YYYY-MM-DD HH:MM:SS' from the schema default.
                # st.date_input wants a date, so take the first 10 chars.
                raw_date = data.get('payment_date') or datetime.date.today().isoformat()
                try:
                    default_payment_date = datetime.date.fromisoformat(raw_date[:10])
                except ValueError:
                    default_payment_date = datetime.date.today()

                payment_date = st.date_input(
                    "Payment Date **`*`**",
                    value=default_payment_date,
                    min_value=MIN_DATE,
                    max_value=MAX_DATE,
                )

                # --- Receipt number ---
                receipt_number = st.text_input(
                    "Receipt Number",
                    value=data.get('receipt_number') or '',
                    help="Leave empty for no receipt. Must be unique if set.",
                )

                # --- Notes ---
                notes = st.text_area(
                    "Notes",
                    value=data.get('notes') or '',
                )

                # --- Status ---
                status_options = ['paid', 'refunded', 'voided']
                current_status = data.get('status', 'paid')
                default_status_index = (
                    status_options.index(current_status)
                    if current_status in status_options
                    else 0
                )
                status = st.selectbox(
                    "Status",
                    options=status_options,
                    index=default_status_index,
                )

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Payment",
                        use_container_width=True,
                    )

                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel",
                        use_container_width=True,
                    ):
                        st.session_state.show_edit_form = False
                        logger.info("Payment edit cancelled: id=%s", payment_id)
                        st.rerun()

                if submitted:
                    # --- Validate required fields ---
                    if selected_student_id is None:
                        st.error("Student is required.")
                    else:
                        try:
                            updates = {
                                'student_id': selected_student_id,
                                'amount_paid': int(amount_paid),
                                'payment_date': payment_date.isoformat(),
                                'method': method,
                                'payment_category': payment_category,
                                'receipt_number': receipt_number.strip() or None,
                                'notes': notes.strip() or None,
                                'status': status,
                            }

                            success = payments.update_payment(payment_id, **updates)

                            if success:
                                logger.info(
                                    "Payment updated successfully: id=%s, "
                                    "student_id=%s, amount=%s",
                                    payment_id,
                                    selected_student_id,
                                    amount_paid,
                                )
                                st.success(
                                    f"✅ Payment {payment_id} updated successfully!"
                                )
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Payment {payment_id} not found. "
                                    "It may have been deleted."
                                )

                        except ValueError as e:
                            logger.warning(
                                "Validation failed for payment update id=%s: %s",
                                payment_id,
                                e,
                            )
                            st.error(f"Validation error: {e}")

                        except Exception:
                            logger.exception(
                                "Database error while updating payment id=%s",
                                payment_id,
                            )
                            st.error(
                                "An unexpected error occurred. Check logs."
                            )


# --- Display table with row selection ---
active_df = None
event = None

if st.session_state.search_results is None:
    active_df = load_table_data(DB_PATH, "payments")
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
            schema=payments.ALLOWED_PAYMENTS_FIELDS,
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
        logger.warning(
            "Stale row selection: index=%s, height=%s — clearing",
            row_idx,
            active_df.height,
        )
        #st.session_state.selected_row_id = None
else:
    pass
    #st.session_state.selected_row_id = None


# --- Delete Payment Form ---
if st.session_state.show_delete_form:
    payment_id = st.session_state.selected_row_id['id']
    student_name = (
        f"{st.session_state.selected_row_id.get('student_first_name', '')} "
        f"{st.session_state.selected_row_id.get('student_last_name', '')}"
    ).strip() or f"Student #{st.session_state.selected_row_id.get('student_id', '?')}"
    amount = st.session_state.selected_row_id.get('amount_paid', '?')
    payment_date = st.session_state.selected_row_id.get('payment_date', '?')
    method = st.session_state.selected_row_id.get('method', '?')
    category = st.session_state.selected_row_id.get('payment_category', '?')
    status = st.session_state.selected_row_id.get('status', '?')
    receipt = st.session_state.selected_row_id.get('receipt_number')

    with st.container():
        st.warning("⚠️ **Delete Payment**")
        st.write(
            f"Are you sure you want to permanently delete the payment of "
            f"**{amount}** from **{student_name}** on **{payment_date}**?"
        )
        st.caption(
            f"Method: `{method}` · Category: `{category}` · "
            f"Status: `{status}`"
        )

        # --- Advisory: distinguish "real payment" from "typo" ---
        if status == 'paid' and receipt:
            st.error(
                f"**This payment has a receipt ({receipt}).** Deleting it "
                f"will orphan the receipt number — the receipt book will "
                f"show a number that no longer exists in the system. If the "
                f"payment was real, **void** it instead (edit form → status "
                f"= `voided`) — that preserves the record and keeps the "
                f"ledger coherent."
            )
        elif status == 'paid':
            st.info(
                "If this payment was real — money changed hands, the student "
                "knows about it — **void** it instead (edit form → status = "
                "`voided`). Delete is only for entries that never should "
                "have existed."
            )

        st.caption(
            "Any credit entries linked to this payment will keep their "
            "records but lose the reference to it (`payment_id` becomes "
            "`NULL`)."
        )

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button(
                "🗑️ Yes, Delete Permanently",
                use_container_width=True,
                type="primary",
            ):
                try:
                    if payments.delete_payment(payment_id):
                        st.success("✅ Payment deleted successfully!")
                        st.session_state.show_delete_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.search_results = None
                        st.rerun()
                    else:
                        st.warning(
                            "That payment no longer exists. It may have "
                            "been deleted in another session."
                        )
                        st.session_state.show_delete_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.search_results = None
                        st.rerun()
                except Exception as e:
                    st.error(f"Error deleting payment: {e}")

        with col_btn2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_delete_form = False
                st.rerun()