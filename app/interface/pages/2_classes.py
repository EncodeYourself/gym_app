from datetime import datetime
import polars as pl
import streamlit as st
from app.interface.utils.logging import get_logger
import app.crud.classes as classes
from app.interface.config import DB_PATH
from app.interface.utils.functions import parse_time_str
import sqlite3
logger = get_logger(__name__)

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

if st.session_state.show_add_form:
    with st.container():
        st.write("### Add New Class")
        st.markdown("*Required fields are marked with **`*`**")

        with st.form("add_class_form"):
            # Required fields
            name = st.text_input("Class Name **`*`**")
            instructor = st.text_input("Instructor **`*`**")

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

            duration_minutes = st.number_input(
                "Duration (minutes)",
                min_value=15,
                max_value=240,
                value=DEFAULT_DURATION,
                step=15,
            )

            description = st.text_area("Description")

            is_active = st.checkbox("Active", value=True)

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
                # Validate required fields
                if not name.strip():
                    st.error("Class Name is required.")
                elif not instructor.strip():
                    st.error("Instructor is required.")
                elif start_time is None:
                    st.error("Start Time is required.")
                else:
                    try:
                        # Format time to HH:MM string
                        time_str = start_time.strftime("%H:%M")

                        new_id = classes.add_class(
                            name=name.strip(),
                            instructor=instructor.strip(),
                            schedule_day=schedule_day,
                            start_time=time_str,
                            duration_minutes=int(duration_minutes),
                            description=description.strip() if description else None,
                            is_active=1 if is_active else 0,
                        )

                        logger.info(
                            "Class added successfully: id=%s, name=%s, day=%s, time=%s",
                            new_id,
                            name.strip(),
                            schedule_day,
                            time_str,
                        )

                        st.success(f"✅ Class added successfully! ID: {new_id}")
                        st.session_state.show_add_form = False
                        st.rerun()

                    except ValueError as e:
                        logger.warning(
                            "Validation failed for class creation: %s",
                            e,
                        )
                        st.error(f"Validation error: {e}")

                    except Exception as e:
                        logger.exception(
                            "Database error while adding class: name=%s",
                            name.strip(),
                        )
                        st.error("An unexpected error occurred. Check logs.")

if st.session_state.show_edit_form:
    class_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No class selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        logger.warning("Edit class form opened without selected class")
        st.rerun()
    else:
        with st.container():
            st.write("### Edit Class")
            st.markdown("*Required fields are marked with **`*`**")

            with st.form("edit_class_form"):
                # Pre-fill all fields
                name = st.text_input(
                    "Class Name **`*`**",
                    value=data.get('name', ''),
                )

                instructor = st.text_input(
                    "Instructor **`*`**",
                    value=data.get('instructor', ''),
                )

                col_day, col_time = st.columns(2)

                with col_day:
                    # Selectbox for schedule day with stored value
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
                    # Time input with stored value
                    current_time_str = data.get('start_time', '00:00')
                    current_time = parse_time_str(current_time_str)
                    start_time = st.time_input(
                        "Start Time **`*`**",
                        value=current_time,
                    )

                duration_minutes = st.number_input(
                    "Duration (minutes)",
                    min_value=15,
                    max_value=240,
                    value=int(data.get('duration_minutes', 90)),
                    step=15,
                )

                description = st.text_area(
                    "Description",
                    value=data.get('description') or '',
                )

                # Checkbox for active status
                is_active = st.checkbox(
                    "Active",
                    value=bool(data.get('is_active', 1)),
                )

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
                        st.session_state.selected_row_id = None
                        st.session_state.edit_row_id = None
                        logger.info(
                            "Class edit cancelled: id=%s",
                            class_id,
                        )
                        st.rerun()

                if submitted:
                    # Validate required fields
                    if not name.strip():
                        st.error("Class Name is required.")
                    elif not instructor.strip():
                        st.error("Instructor is required.")
                    else:
                        try:
                            time_str = start_time.strftime("%H:%M")

                            updates = {
                                'name': name.strip(),
                                'instructor': instructor.strip(),
                                'schedule_day': schedule_day,
                                'start_time': time_str,
                                'duration_minutes': int(duration_minutes),
                                'description': (
                                    description.strip()
                                    if description else None
                                ),
                                'is_active': 1 if is_active else 0,
                            }

                            success = classes.update_class(
                                class_id,
                                **updates,
                            )

                            if success:
                                logger.info(
                                    "Class updated successfully: id=%s, "
                                    "name=%s, day=%s, time=%s",
                                    class_id,
                                    name.strip(),
                                    schedule_day,
                                    time_str,
                                )

                                st.success(
                                    f"✅ Class {class_id} updated "
                                    "successfully!"
                                )

                                # Clear edit state and refresh
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
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
                                "Database error while updating class "
                                "id=%s",
                                class_id,
                            )
                            st.error(
                                "An unexpected error occurred. "
                                "Check logs."
                            )
if st.session_state.search_results is None:
    df = load_table_data(DB_PATH, "classes")

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