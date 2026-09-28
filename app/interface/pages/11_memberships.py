from app.database.database_ctl import get_connection
import app.crud.payments as memberships
import app.crud.payments as students
import app.crud.payments as plans
import datetime
import polars as pl
import streamlit as st
import sqlite3
from typing import Any, Dict, List

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
    page_title="Membership",
    layout="wide"
)

MIN_DATE = datetime.date(1970, 1, 1)
MAX_DATE = datetime.date.today()

with st.sidebar:
    if st.button("🔎 Search Membership"):
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
                            results = memberships.search_membership(search_term)
                            
                        st.session_state.search_results = results

    if st.button("Add Membership"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Membership'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a class first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Membership'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a class row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form

def compute_expiry_date(start_date: datetime.date, plan: Dict[str, Any]) -> datetime.date:
    """
    Derive a membership's expiry_date from its start_date and plan.

    Single-session plans expire on the start date (one day of access).
    Plans with a duration_weeks value expire that many weeks later.
    """
    if plan.get('is_single'):
        return start_date
    weeks = plan.get('duration_weeks')
    if not weeks:
        # Schema requires duration_weeks for non-single plans, so this
        # shouldn't happen — but don't silently invent a date if it does.
        raise ValueError(
            f"Plan {plan.get('id')} has no duration_weeks and is not single."
        )
    return start_date + datetime.timedelta(weeks=weeks)


if st.session_state.show_add_membership_form:
    with st.container():
        st.write("### New Membership")
        st.markdown("*Required fields are marked with **`*`**")

        # --- Load reference data ---
        try:
            students_list = students.find_students()
            plans_list = plans.find_plans(is_active=1)
        except Exception as e:
            st.error(f"Could not load reference data: {e}")
            students_list, plans_list = [], []

        if not students_list or not plans_list:
            st.warning(
                "You need at least one active student and one active plan "
                "before adding a membership."
            )
        else:
            students_by_id = {s["id"]: s for s in students_list}
            plans_by_id = {p["id"]: p for p in plans_list}

            # --- Setup widgets OUTSIDE the form ---
            # These drive the expiry preview and the duplicate-membership
            # warning below, so they need to trigger a rerun on change.
            student_id = st.selectbox(
                "Student **`*`**",
                options=list(students_by_id),
                format_func=lambda sid: (
                    f'{students_by_id[sid]["last_name"]} '
                    f'{students_by_id[sid]["first_name"]} '
                    f'({students_by_id[sid].get("phone") or "no phone"})'
                ),
            )

            plan_id = st.selectbox(
                "Plan **`*`**",
                options=list(plans_by_id),
                format_func=lambda pid: (
                    f'{plans_by_id[pid]["name"]} — '
                    f'{plans_by_id[pid]["price"]}'
                ),
            )

            start_date = st.date_input(
                "Start Date **`*`**",
                value=datetime.date.today(),
                min_value=MIN_DATE,
                max_value=MAX_DATE,
            )

            # --- Compute and show expiry preview ---
            selected_plan = plans_by_id[plan_id]
            try:
                expiry_date = compute_expiry_date(start_date, selected_plan)
                st.info(
                    f"This membership will run from "
                    f"**{start_date.isoformat()}** to "
                    f"**{expiry_date.isoformat()}** "
                    f"({selected_plan.get('duration_weeks') or '—'} weeks)."
                )
            except ValueError as e:
                st.error(str(e))
                expiry_date = None

            # --- Advisory: student already has an active membership ---
            existing = []
            if expiry_date is not None:
                try:
                    existing = memberships.find_membership(
                        student_id=student_id, status='active'
                    )
                except Exception as e:
                    st.warning(f"Could not check for existing memberships: {e}")

            if existing:
                st.warning(
                    f"**{students_by_id[student_id]['first_name']}** already "
                    f"has an active membership. If this is an upgrade, use the "
                    f"upgrade flow instead — otherwise you'll end up with two "
                    f"overlapping memberships."
                )

            # --- Form: only the notes and the commit ---
            with st.form("add_membership_form"):
                notes = st.text_area("Notes")

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Save Membership", use_container_width=True
                    )
                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel", use_container_width=True
                    ):
                        st.session_state.show_add_membership_form = False
                        st.rerun()

                if submitted:
                    if expiry_date is None:
                        st.error(
                            "Cannot save: the selected plan has no valid "
                            "duration."
                        )
                    else:
                        try:
                            new_id = memberships.add_membership(
                                student_id=student_id,
                                plan_id=plan_id,
                                start_date=start_date.isoformat(),
                                expiry_date=expiry_date.isoformat(),
                                notes=notes.strip() or None,
                            )
                            st.success(
                                f"✅ Membership added successfully! ID: {new_id}"
                            )
                            st.session_state.show_add_membership_form = False
                            st.session_state.membership_search_results = None
                            st.rerun()
                        except ValueError as e:
                            st.error(f"Validation error: {e}")
                        except Exception as e:
                            st.error(f"Database error: {e}")