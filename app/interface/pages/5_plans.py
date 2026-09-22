import streamlit as st
import polars as pl
import sqlite3
from app.crud import plans
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
    page_title="Plans",
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
    if st.button("🔎 Search Plans"):
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
                            results = plans.find_plans(search_term.strip())
                        st.session_state.search_results = results
    
    if st.button("Add Plan"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Plan'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a plan row first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Plan'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a plan row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form

# --- Add Plan Form ---
if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Plan")
        st.markdown("*Required fields are marked with **`*`**")

        # Plan type is OUTSIDE the form: it drives which fields render below,
        # and Streamlit forms don't rerun on internal widget changes.
        # Three concrete types map cleanly to the schema's CHECK constraints.
        plan_type = st.radio(
            "Plan Type **`*`**",
            options=["monthly", "unlimited", "single"],
            format_func=lambda t: {
                "monthly": "Monthly (limited trainings)",
                "unlimited": "Monthly unlimited",
                "single": "Single session",
            }[t],
            horizontal=True,
        )

        with st.form("add_plan_form"):
            name = st.text_input("Plan Name **`*`**")
            price = st.number_input(
                "Price **`*`**", min_value=0, step=100, value=0
            )

            # --- Conditional fields driven by plan_type ---
            if plan_type == "monthly":
                duration_weeks = st.number_input(
                    "Duration (weeks) **`*`**",
                    min_value=1, max_value=52, value=4, step=1,
                )
                max_trainings = st.number_input(
                    "Max Trainings **`*`**",
                    min_value=1, max_value=100, value=8, step=1,
                )
            elif plan_type == "unlimited":
                duration_weeks = st.number_input(
                    "Duration (weeks) **`*`**",
                    min_value=1, max_value=52, value=4, step=1,
                )
                max_trainings = None
            else:  # single
                duration_weeks = None
                max_trainings = None
                st.caption("Single sessions have no duration and no training cap.")

            is_active = st.checkbox("Active", value=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button(
                    "💾 Save Plan", use_container_width=True
                )
            with col_btn2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.show_add_form = False
                    st.rerun()

            if submitted:
                if not name.strip():
                    st.error("Plan Name is required.")
                else:
                    try:
                        new_id = plans.add_plan(
                            name=name.strip(),
                            price=int(price),
                            duration_weeks=duration_weeks,
                            max_trainings=max_trainings,
                            is_unlimited=1 if plan_type == "unlimited" else 0,
                            is_single=1 if plan_type == "single" else 0,
                            is_active=1 if is_active else 0,
                        )
                        st.success(f"✅ Plan '{name.strip()}' added successfully!")
                        st.session_state.show_add_form = False
                        st.session_state.search_results = None
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Validation error: {e}")
                    except Exception as e:
                        st.error(f"Database error: {e}")

# --- Display table with row selection ---
active_df = None
event = None

if st.session_state.search_results is None:
    active_df = load_table_data(DB_PATH, "plans")
    st.markdown(f"**Total plans:** {active_df.height:,}")
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
            schema=plans.ALLOWED_PLAN_FIELDS,
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
        st.session_state.selected_row_id = None
else:
    st.session_state.selected_row_id = None

# --- Edit Plan Form ---
if st.session_state.show_edit_form:
    plan_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No plan selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        st.rerun()
    else:
        with st.container():
            st.write("### Edit Plan")
            st.markdown("*Required fields are marked with **`*`**")

            # --- Determine current plan type from stored flags ---
            if bool(data.get('is_single', 0)):
                current_type = "single"
            elif bool(data.get('is_unlimited', 0)):
                current_type = "unlimited"
            else:
                current_type = "monthly"

            # Plan type MUST be outside the form: changing it re-renders
            # the conditional fields below, which a form cannot do.
            plan_type = st.radio(
                "Plan Type **`*`**",
                options=["monthly", "unlimited", "single"],
                format_func=lambda t: {
                    "monthly": "Monthly (limited trainings)",
                    "unlimited": "Monthly unlimited",
                    "single": "Single session",
                }[t],
                index=["monthly", "unlimited", "single"].index(current_type),
                horizontal=True,
                key=f"edit_plan_type_{plan_id}",
            )

            with st.form(f"edit_plan_form_{plan_id}"):
                # --- Fields present for all plan types ---
                name = st.text_input(
                    "Plan Name **`*`**",
                    value=data.get('name', ''),
                )
                price = st.number_input(
                    "Price **`*`**",
                    min_value=0,
                    step=100,
                    value=int(data.get('price') or 0),
                )

                # --- Conditional fields ---
                if plan_type == "monthly":
                    duration_weeks = st.number_input(
                        "Duration (weeks) **`*`**",
                        min_value=1,
                        max_value=52,
                        value=int(data.get('duration_weeks') or 4),
                        step=1,
                    )
                    max_trainings = st.number_input(
                        "Max Trainings **`*`**",
                        min_value=1,
                        max_value=100,
                        value=int(data.get('max_trainings') or 8),
                        step=1,
                    )
                elif plan_type == "unlimited":
                    duration_weeks = st.number_input(
                        "Duration (weeks) **`*`**",
                        min_value=1,
                        max_value=52,
                        value=int(data.get('duration_weeks') or 4),
                        step=1,
                    )
                    max_trainings = None
                else:  # single
                    duration_weeks = None
                    max_trainings = None
                    st.caption(
                        "Single sessions have no duration and no training cap."
                    )

                is_active = st.checkbox(
                    "Active",
                    value=bool(data.get('is_active', 1)),
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Plan", use_container_width=True
                    )
                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel", use_container_width=True
                    ):
                        st.session_state.show_edit_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.edit_row_id = None
                        st.rerun()

                if submitted:
                    if not name.strip():
                        st.error("Plan Name is required.")
                    else:
                        try:
                            updates = {
                                'name': name.strip(),
                                'price': int(price),
                                'duration_weeks': duration_weeks,
                                'max_trainings': max_trainings,
                                'is_unlimited': 1 if plan_type == "unlimited" else 0,
                                'is_single': 1 if plan_type == "single" else 0,
                                'is_active': 1 if is_active else 0,
                            }
                            success = plans.update_plan(plan_id, **updates)
                            if success:
                                st.success(
                                    f"✅ Plan '{name.strip()}' updated successfully!"
                                )
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Plan {plan_id} not found. "
                                    "It may have been deleted."
                                )
                        except ValueError as e:
                            st.error(f"Validation error: {e}")
                        except Exception as e:
                            st.error(f"Database error: {e}")

# --- Delete Plan Form ---
if st.session_state.show_delete_form:
    plan_id = st.session_state.selected_row_id['id']
    plan_name = st.session_state.selected_row_id.get('name', '?')
    plan_price = st.session_state.selected_row_id.get('price')

    with st.container():
        st.warning(f"⚠️ **Delete Plan**")
        st.write(
            f"Are you sure you want to permanently delete "
            f"**{plan_name}**?"
        )
        st.write(
            "This action **cannot be undone**. Plans that have been used "
            "in any payment cannot be deleted — deactivate them instead."
        )

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button(
                "🗑️ Yes, Delete Permanently",
                use_container_width=True,
                type="primary",
            ):
                try:
                    if plans.delete_plan(plan_id):
                        st.success(f"✅ Plan '{plan_name}' deleted successfully!")
                        st.session_state.show_delete_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.search_results = None
                        st.rerun()
                    else:
                        st.warning(
                            "That plan no longer exists. It may have been "
                            "deleted in another session."
                        )
                        st.session_state.show_delete_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.search_results = None
                        st.rerun()
                except ValueError as e:
                    # Most likely: FK constraint from payments
                    st.error(f"Cannot delete plan: {e}")
                except Exception as e:
                    st.error(f"Error deleting plan: {e}")

        with col_btn2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_delete_form = False
                st.rerun()