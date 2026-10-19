from datetime import datetime
import polars as pl
import streamlit as st
from app.interface.utils.logging import get_logger
import app.crud.classes as classes
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
    page_title="Classes Table",
    page_icon="👨‍🎓",
    layout="wide"
)
DEFAULT_DURATION = 90
def create_timetable(df):
    """Convert classes DataFrame to timetable format - removes empty rows"""
    
    df_active = df.filter(pl.col('is_active') == 1)
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Get all unique times from active classes
    all_times = df_active.select('start_time').unique().sort('start_time').to_series().to_list()
    
    # Get days that have classes
    active_days = df_active['schedule_day'].unique().to_list()
    
    timetable_dict = {}
    
    for row in df_active.iter_rows(named=True):
        day = row['schedule_day']
        time_key = row['start_time']
        
        # Format with line breaks
        cell_content = f"""
        {row['id']}.    {row['name']} ({row['instructor']})
        """
        
        timetable_dict[(day, time_key)] = cell_content
    
    # Build timetable with only days that have classes
    header = ['Time'] + [day for day in days_order if day in active_days]
    timetable_data = [header]
    
    # For each time slot, create a row only if it has classes
    for time_slot in all_times:
        row = [time_slot]
        has_class = False
        
        for day in header[1:]:
            cell = timetable_dict.get((day, time_slot), '')
            row.append(cell)
            if cell:
                has_class = True
        
        # Only add row if it has at least one class
        if has_class:
            timetable_data.append(row)
    
    return timetable_data


with st.sidebar:
    if st.button("🔎 Search Class"):
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
                            results = classes.find_classes(search_term)
                            
                        st.session_state.search_results = results

    if st.button("Add Class"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Class'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a class first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Class'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a class row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form
# Create the timetable
# --- Add Class Form ---
if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Class")
        st.markdown("*Required fields are marked with **`*`**")

        # --- Load trainers for the FK dropdown ---
        try:
            trainers_list = trainers.find_trainers()
        except Exception as e:
            st.error(f"Could not load trainers: {e}")
            trainers_list = []

        if not trainers_list:
            st.warning(
                "You need at least one trainer before adding a class. "
                "Add a trainer first."
            )
        else:
            trainers_by_id = {t["id"]: t for t in trainers_list}

            def _trainer_label(tid: int) -> str:
                t = trainers_by_id[tid]
                suffix = (
                    "" if t.get("status") == "active"
                    else "  (inactive)"
                )
                return (
                    f'{t["last_name"]} {t["first_name"]} '
                    f'(ID {tid}){suffix}'
                )

            with st.form("add_class_form"):
                # --- Class name ---
                name = st.text_input("Class Name **`*`**")

                # --- Instructor selectbox (FK to trainers) ---
                instructor_id = st.selectbox(
                    "Instructor **`*`**",
                    options=list(trainers_by_id),
                    format_func=_trainer_label,
                    help="Only active trainers should be assigned new classes.",
                )

                # --- Day + Time ---
                col_day, col_time = st.columns(2)
                with col_day:
                    schedule_day = st.selectbox(
                        "Schedule Day **`*`**",
                        options=classes.VALID_DAYS,
                    )
                with col_time:
                    start_time = st.time_input(
                        "Start Time **`*`**",
                        value=None,
                    )

                # --- Duration ---
                duration_minutes = st.number_input(
                    "Duration (minutes)",
                    min_value=15,
                    max_value=240,
                    value=DEFAULT_DURATION,
                    step=15,
                )

                # --- Description ---
                description = st.text_area("Description")

                # --- Active flag ---
                is_active = st.checkbox("Active", value=True)

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Save Class",
                        use_container_width=True,
                    )
                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel",
                        use_container_width=True,
                    ):
                        st.session_state.show_add_form = False
                        logger.info("Class creation cancelled by user")
                        st.rerun()

                if submitted:
                    # --- Validate required fields ---
                    if not name.strip():
                        st.error("Class Name is required.")
                    elif instructor_id is None:
                        st.error("Instructor is required.")
                    elif start_time is None:
                        st.error("Start Time is required.")
                    else:
                        try:
                            time_str = start_time.strftime("%H:%M")

                            new_id = classes.add_class(
                                name=name.strip(),
                                instructor_id=instructor_id,
                                schedule_day=schedule_day,
                                start_time=time_str,
                                duration_minutes=int(duration_minutes),
                                description=(
                                    description.strip()
                                    if description else None
                                ),
                                is_active=1 if is_active else 0,
                            )

                            logger.info(
                                "Class added successfully: id=%s, "
                                "name=%s, instructor_id=%s, day=%s, time=%s",
                                new_id,
                                name.strip(),
                                instructor_id,
                                schedule_day,
                                time_str,
                            )

                            st.success(
                                f"✅ Class added successfully! ID: {new_id}"
                            )
                            st.session_state.show_add_form = False
                            st.session_state.search_results = None
                            st.rerun()

                        except ValueError as e:
                            logger.warning(
                                "Validation failed for class creation: %s",
                                e,
                            )
                            st.error(f"Validation error: {e}")

                        except Exception:
                            logger.exception(
                                "Database error while adding class: name=%s",
                                name.strip(),
                            )
                            st.error(
                                "An unexpected error occurred. Check logs."
                            )

# --- Edit Class Form ---
if st.session_state.show_edit_form:
    class_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No class selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        logger.warning("Edit class form opened without selected class")
        st.rerun()
    else:
        # --- Load trainers for the FK selectbox ---
        try:
            trainers_list = trainers.find_trainers()
        except Exception as e:
            st.error(f"Could not load trainers: {e}")
            trainers_list = []

        trainers_by_id = {t["id"]: t for t in trainers_list}
        current_instructor_id = data.get('instructor_id')

        with st.container():
            st.write("### Edit Class")
            st.markdown("*Required fields are marked with **`*`**")

            with st.form(f"edit_class_form_{class_id}"):
                # --- Class name ---
                name = st.text_input(
                    "Class Name **`*`**",
                    value=data.get('name', ''),
                )

                # --- Instructor selectbox ---
                if trainers_by_id:
                    trainer_options = list(trainers_by_id.keys())
                    if current_instructor_id not in trainer_options:
                        # Two cases: originally unassigned (None), or the
                        # linked trainer was removed from the trainers list.
                        if current_instructor_id is not None:
                            st.warning(
                                f"Currently assigned to trainer "
                                f"{current_instructor_id}, which is not "
                                f"in the list. Please pick a trainer."
                            )
                        default_instructor_index = 0
                    else:
                        default_instructor_index = trainer_options.index(
                            current_instructor_id
                        )

                    def _trainer_label(tid: int) -> str:
                        t = trainers_by_id[tid]
                        suffix = (
                            "" if t.get("status") == "active"
                            else "  (inactive)"
                        )
                        return (
                            f'{t["last_name"]} {t["first_name"]} '
                            f'(ID {tid}){suffix}'
                        )

                    instructor_id = st.selectbox(
                        "Instructor **`*`**",
                        options=trainer_options,
                        index=default_instructor_index,
                        format_func=_trainer_label,
                    )
                else:
                    st.warning(
                        "No trainers available. You cannot assign an "
                        "instructor right now."
                    )
                    instructor_id = None

                # --- Day + Time ---
                col_day, col_time = st.columns(2)

                with col_day:
                    current_day = data.get('schedule_day', 'Monday')
                    default_day_index = (
                        list(classes.VALID_DAYS).index(current_day)
                        if current_day in classes.VALID_DAYS
                        else 0
                    )
                    schedule_day = st.selectbox(
                        "Schedule Day **`*`**",
                        options=classes.VALID_DAYS,
                        index=default_day_index,
                    )

                with col_time:
                    current_time_str = data.get('start_time', '00:00')
                    current_time = parse_time_str(current_time_str)
                    start_time = st.time_input(
                        "Start Time **`*`**",
                        value=current_time,
                    )

                # --- Duration ---
                duration_minutes = st.number_input(
                    "Duration (minutes)",
                    min_value=15,
                    max_value=240,
                    value=int(data.get('duration_minutes', 90)),
                    step=15,
                )

                # --- Description ---
                description = st.text_area(
                    "Description",
                    value=data.get('description') or '',
                )

                # --- Active flag ---
                is_active = st.checkbox(
                    "Active",
                    value=bool(data.get('is_active', 1)),
                )

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)

                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Class",
                        use_container_width=True,
                    )

                with col_btn2:
                    if st.form_submit_button(
                        "❌ Cancel",
                        use_container_width=True,
                    ):
                        st.session_state.show_edit_form = False
                        
                        logger.info("Class edit cancelled: id=%s", class_id)
                        st.rerun()

                if submitted:
                    # --- Validate required fields ---
                    if not name.strip():
                        st.error("Class Name is required.")
                    elif instructor_id is None:
                        st.error("Instructor is required.")
                    else:
                        try:
                            time_str = start_time.strftime("%H:%M")

                            updates = {
                                'name': name.strip(),
                                'instructor_id': instructor_id,
                                'schedule_day': schedule_day,
                                'start_time': time_str,
                                'duration_minutes': int(duration_minutes),
                                'description': (
                                    description.strip()
                                    if description else None
                                ),
                                'is_active': 1 if is_active else 0,
                            }

                            success = classes.update_class(class_id, **updates)

                            if success:
                                logger.info(
                                    "Class updated successfully: id=%s, "
                                    "name=%s, instructor_id=%s, day=%s, time=%s",
                                    class_id,
                                    name.strip(),
                                    instructor_id,
                                    schedule_day,
                                    time_str,
                                )

                                st.success(
                                    f"✅ Class {class_id} updated successfully!"
                                )

                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.session_state.search_results = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Class {class_id} not found. "
                                    "It may have been deleted."
                                )

                        except ValueError as e:
                            logger.warning(
                                "Validation failed for class update "
                                "id=%s: %s",
                                class_id,
                                e,
                            )
                            st.error(f"Validation error: {e}")

                        except Exception:
                            logger.exception(
                                "Database error while updating class id=%s",
                                class_id,
                            )
                            st.error(
                                "An unexpected error occurred. Check logs."
                            )
# --- Display table with row selection ---
active_df = None
event = None

if st.session_state.search_results is None:
    rows = classes.find_classes()
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
            schema=classes.ALLOWED_CLASSES_FIELDS,
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
            "Stale class selection: index=%s, height=%s — clearing",
            row_idx,
            active_df.height,
        )
        st.session_state.selected_row_id = None
else:
    st.session_state.selected_row_id = None

if st.session_state.show_delete_form:
    class_id = st.session_state.selected_row_id['id']
    class_name = f"{st.session_state.selected_row_id.get('first_name', '')} {st.session_state.selected_row_id.get('last_name', '')}"
    
    with st.container():
        st.warning(f"⚠️ **Delete class**")
        st.write(f"Are you sure you want to permanently delete **{class_name}** (ID: {class_id})?")
        st.write("This action **cannot be undone** and will remove all associated data.")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🗑️ Yes, Delete Permanently", use_container_width=True, type="primary"):
                try:
                    classes.delete_class(class_id)
                    st.success(f"✅ class {class_id} ({class_name}) deleted successfully!")
                    st.session_state.show_delete_form = False
                    st.session_state.selected_row_id = None
                    st.session_state.search_results = None  # Force refresh
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting class: {e}")
        
        with col_btn2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_delete_form = False
                st.rerun()