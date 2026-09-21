from app.database.database_ctl import get_connection
import app.crud.payments as payments
import datetime
import polars as pl
import streamlit as st
import sqlite3

TABLE_PAYMENTS = '''
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    amount_paid INTEGER NOT NULL CHECK (amount_paid >= 0),
    payment_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    method TEXT NOT NULL CHECK (method IN ('cash', 'card', 'bank_transfer', 'other')),
    receipt_number TEXT UNIQUE,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'paid' CHECK (status IN ('paid', 'refunded', 'voided')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT
);
'''

def load_table_data(db_path, table_name):
    conn = sqlite3.connect(db_path)
    query = f'SELECT * FROM {table_name}'
    df = pl.read_database(query, conn)
    conn.close()
    return df


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
MIN_DATE = datetime.date(1970, 1, 1)
MAX_DATE = datetime.date.today()


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
            students_list = students.get_all_students()   # adapt to your API
            plans_list = plans.get_all_plans()            # adapt to your API
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
                        st.session_state.show_add_payment_form = False
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
                        st.session_state.show_add_payment_form = False
                        st.session_state.payment_search_results = None
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")