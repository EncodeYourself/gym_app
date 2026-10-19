from app.database.database_ctl import get_connection
import app.crud.memberships as memberships
import app.crud.students as students
import app.crud.plans as plans
import datetime
import polars as pl
import streamlit as st
import sqlite3
from typing import Any, Dict, List

# Columns shown to the owner. The full row dict — including raw
# student_id and plan_id — still lives in `selected_row_id` for the
# edit/delete forms, but the display is human-readable.
MEMBERSHIP_DISPLAY_COLUMNS = [
    "id",
    "student_last_name",
    "student_first_name",
    "plan_name",
    "start_date",
    "expiry_date",
    "used_trainings",
    "status",
]

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
    page_title="Membership",
    layout="wide"
)


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


if st.session_state.show_add_form:
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


# --- Display table with row selection ---
active_df = None
event = None

if st.session_state.search_results is None:
    try:
        rows = memberships.find_membership()
    except Exception as e:
        st.error(f"Could not load memberships: {e}")
        rows = []

    if rows:
        active_df = pl.DataFrame(rows)
        st.markdown(f"**Total memberships:** {active_df.height:,}")

        display_df = active_df.select(
            [c for c in MEMBERSHIP_DISPLAY_COLUMNS if c in active_df.columns]
        )
        event = st.dataframe(
            display_df,
            selection_mode="single-row",
            on_select="rerun",
            key="membership_main_table",
        )
    else:
        st.info("No memberships found.")
else:
    if len(st.session_state.search_results) > 0:
        active_df = pl.DataFrame(st.session_state.search_results)

        display_df = active_df.select(
            [c for c in MEMBERSHIP_DISPLAY_COLUMNS if c in active_df.columns]
        )
        event = st.dataframe(
            display_df,
            selection_mode="single-row",
            on_select="rerun",
            key="membership_search_table",
        )
    else:
        st.info("No matching memberships found.")

# --- Capture selection (bounds-checked against the full frame) ---
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
            "Stale membership selection: index=%s, height=%s — clearing",
            row_idx,
            active_df.height,
        )
        st.session_state.selected_row_id = None
else:
    st.session_state.selected_row_id = None

# --- Edit Membership Form ---
if st.session_state.show_edit_form:
    membership_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No membership selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        st.rerun()
    else:
        # --- Load reference data for the FK dropdowns ---
        # Students: all, not just active. The owner may be editing a
        # membership for a student who was later suspended.
        # Plans: all, not just active. The current plan may have been
        # deactivated since the membership was created, and we must
        # still be able to display and keep it.
        try:
            students_list = students.find_students()
        except Exception as e:
            st.error(f"Could not load students: {e}")
            students_list = []

        try:
            plans_list = plans.find_plans()
        except Exception as e:
            st.error(f"Could not load plans: {e}")
            plans_list = []

        students_by_id = {s["id"]: s for s in students_list}
        plans_by_id = {p["id"]: p for p in plans_list}

        current_student_id = data.get('student_id')
        current_plan_id = data.get('plan_id')

        with st.container():
            st.write("### Edit Membership")
            st.markdown("*Required fields are marked with **`*`**")

            # --- Read-only context ---
            # The owner needs to know *which* membership they're editing.
            # The row dict from find_membership carries the display names
            # so we can show them without another query.
            student_label = (
                f'{data.get("student_last_name", "")} '
                f'{data.get("student_first_name", "")}'
            ).strip() or f'Student #{current_student_id}'
            st.caption(f"Editing membership for **{student_label}** "
                       f"(ID: {membership_id})")

            with st.form(f"edit_membership_form_{membership_id}"):
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
                    )
                else:
                    st.warning("No students available.")
                    selected_student_id = None

                # --- Plan selectbox ---
                if plans_by_id:
                    plan_options = list(plans_by_id.keys())
                    if current_plan_id not in plan_options:
                        st.warning(
                            f"Original plan (id={current_plan_id}) "
                            "no longer exists. Please pick another."
                        )
                        default_plan_index = 0
                    else:
                        default_plan_index = plan_options.index(current_plan_id)

                    def _plan_label(pid: int) -> str:
                        p = plans_by_id[pid]
                        suffix = "" if p.get("is_active", 1) else "  (inactive)"
                        return f'{p["name"]} — {p["price"]}{suffix}'

                    selected_plan_id = st.selectbox(
                        "Plan **`*`**",
                        options=plan_options,
                        index=default_plan_index,
                        format_func=_plan_label,
                    )
                else:
                    st.warning("No plans available.")
                    selected_plan_id = None

                # --- Dates ---
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    start_date = st.date_input(
                        "Start Date **`*`**",
                        value=datetime.date.fromisoformat(
                            data.get('start_date') or datetime.date.today().isoformat()
                        ),
                        min_value=MIN_DATE,
                        max_value=MAX_DATE,
                    )
                with col_d2:
                    expiry_date = st.date_input(
                        "Expiry Date **`*`**",
                        value=datetime.date.fromisoformat(
                            data.get('expiry_date') or datetime.date.today().isoformat()
                        ),
                        min_value=MIN_DATE,
                        max_value=MAX_DATE,
                    )

                # --- Used trainings ---
                used_trainings = st.number_input(
                    "Used Trainings",
                    min_value=0,
                    max_value=1000,
                    value=int(data.get('used_trainings') or 0),
                    step=1,
                )

                # --- Status ---
                # Selectbox, not radio: six options is too many to lay out
                # horizontally without wrapping on narrow screens.
                status_options = [
                    'active', 'on_hold', 'expired',
                    'completed', 'cancelled', 'upgraded',
                ]
                current_status = data.get('status', 'active')
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

                # --- Notes ---
                notes = st.text_area("Notes", value=data.get('notes') or '')

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Membership", use_container_width=True
                    )
                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel", use_container_width=True
                    ):
                        st.session_state.show_edit_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.edit_row_id = None
                        st.rerun()

                # --- Submit ---
                if submitted:
                    if selected_student_id is None:
                        st.error("Student is required.")
                    elif selected_plan_id is None:
                        st.error("Plan is required.")
                    elif expiry_date < start_date:
                        st.error(
                            "Expiry date cannot be before the start date."
                        )
                    else:
                        try:
                            updates = {
                                'student_id': selected_student_id,
                                'plan_id': selected_plan_id,
                                'start_date': start_date.isoformat(),
                                'expiry_date': expiry_date.isoformat(),
                                'used_trainings': int(used_trainings),
                                'status': status,
                                'notes': notes.strip() or None,
                            }

                            success = memberships.update_membership(
                                membership_id, **updates
                            )

                            if success:
                                st.success(
                                    "✅ Membership updated successfully!"
                                )
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Membership {membership_id} not found. "
                                    "It may have been deleted."
                                )

                        except ValueError as e:
                            st.error(f"Validation error: {e}")
                        except Exception as e:
                            st.error(f"Database error: {e}")

# --- Delete Membership Form ---
if st.session_state.show_delete_form:
    membership_id = st.session_state.selected_row_id['id']
    student_name = (
        f"{st.session_state.selected_row_id.get('student_first_name', '')} "
        f"{st.session_state.selected_row_id.get('student_last_name', '')}"
    ).strip() or f"Student #{st.session_state.selected_row_id.get('student_id', '?')}"
    plan_name = st.session_state.selected_row_id.get('plan_name', '?')
    start_date = st.session_state.selected_row_id.get('start_date', '?')
    expiry_date = st.session_state.selected_row_id.get('expiry_date', '?')
    status = st.session_state.selected_row_id.get('status', '?')

    with st.container():
        st.warning("⚠️ **Delete Membership**")
        st.write(
            f"Are you sure you want to delete the **{plan_name}** membership "
            f"for **{student_name}** "
            f"({start_date} → {expiry_date}, status: `{status}`)?"
        )

        # --- Advisory: only if the row is still active ---
        if status == 'active':
            st.info(
                "This membership is currently **active**. If you want to end "
                "it without erasing the record, **Cancel** it instead — that "
                "preserves the history and lets you see when the student "
                "stopped attending. Delete is meant for correcting mistakes, "
                "not for ending a real membership."
            )

        st.caption(
            "Deleting removes only this membership row. Payments remain "
            "recorded and are not affected."
        )

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button(
                "🗑️ Yes, Delete Permanently",
                use_container_width=True,
                type="primary",
            ):
                try:
                    if memberships.delete_membership(membership_id):
                        st.success("✅ Membership deleted successfully!")
                        st.session_state.show_delete_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.search_results = None
                        st.rerun()
                    else:
                        st.warning(
                            "That membership no longer exists. It may have "
                            "been deleted in another session."
                        )
                        st.session_state.show_delete_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.search_results = None
                        st.rerun()
                except Exception as e:
                    st.error(f"Error deleting membership: {e}")

        with col_btn2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_delete_form = False
                st.rerun()