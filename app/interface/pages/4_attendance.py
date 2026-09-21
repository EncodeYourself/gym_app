
import app.crud.students as students
import app.crud.classes as classes
import app.crud.attendance as attendance
import sqlite3
import datetime
import polars as pl
import streamlit as st
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
    page_title="Attendance",
    layout="wide"
)

# Hardcoded database path
DB_PATH = "app/data/business.db"

# Helper function to load data
def load_table_data(db_path):
    conn = sqlite3.connect(db_path)
    query = f'''SELECT
    a.id,
    a.student_id,
    s.last_name   AS student_last_name,
    s.first_name  AS student_first_name,
    a.class_id,
    c.name        AS class_name,
    a.attendance_date,
    a.attendance_type,
    a.notes,
    s.phone       AS student_phone,
    c.schedule_day AS class_day,
    c.start_time  AS class_time,
    a.created_at
    FROM attendance a
    JOIN students s ON s.id = a.student_id
    JOIN classes  c ON c.id = a.class_id
    ORDER BY a.attendance_date DESC, a.id DESC'''
    df = pl.read_database(query, conn)
    conn.close()
    return df



with st.sidebar:
    if st.button("🔎 Search People"):
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
                            results = students.find_students(search_term.strip())
                        st.session_state.search_results = results
    
    if st.button("Add Attendance"):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.session_state.show_edit_form = False
        st.session_state.show_delete_form = False
    
    if st.button('Edit Attendance'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a student row first')
        else: 
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = not st.session_state.show_edit_form
            st.session_state.show_delete_form = False
            st.session_state.edit_row_id = st.session_state.selected_row_id['id']

    if st.button('Delete Attendance'):
        if st.session_state.get('selected_row_id') is None:
            st.warning('Please select a student row first')
        else:
            st.session_state.show_add_form = False
            st.session_state.show_edit_form = False
            st.session_state.show_delete_form = not st.session_state.show_delete_form


if st.session_state.show_add_form:
    with st.container():
        st.write("### Take Attendance")
        st.markdown("*Required fields are marked with **`*`**")

        # Reset counter used to clear all widgets after a successful save.
        if 'attendance_form_counter' not in st.session_state:
            st.session_state.attendance_form_counter = 0
        ver = st.session_state.attendance_form_counter

        # --- Group filter (OUTSIDE form: changing it must reload students) ---
        group_type = st.radio(
            "Group **`*`**",
            options=["adult", "child"],
            horizontal=True,
            key=f"attendance_group_{ver}",
        )

        # --- Load students for the selected group ---
        try:
            students_list = students.find_students(group_type=group_type)
        except Exception as e:
            st.error(f"Could not load students: {e}")
            students_list = []

        students_by_id = {s["id"]: s for s in students_list}

        # --- Load classes once ---
        try:
            classes_list = classes.find_classes()
        except Exception as e:
            st.error(f"Could not load classes: {e}")
            classes_list = []

        classes_by_id = {c["id"]: c for c in classes_list}

        with st.form(f"add_attendance_form_{ver}"):
            # --- Class selection ---
            if classes_by_id:
                class_id = st.selectbox(
                    "Class **`*`**",
                    options=list(classes_by_id),
                    format_func=lambda cid: (
                        f'{classes_by_id[cid].get("schedule_day", "")} '
                        f'{classes_by_id[cid].get("start_time", "")} — '
                        f'{classes_by_id[cid].get("name", "")}'
                    ),
                )
            else:
                st.warning("No classes available. Add a class first.")
                class_id = None

            # --- Date ---
            attendance_date = st.date_input(
                "Date **`*`**",
                value=datetime.date.today(),
                min_value=MIN_DATE,
                max_value=MAX_DATE,
            )

            # --- Student multiselect ---
            if students_by_id:
                selected_ids = st.multiselect(
                    "Students present **`*`**",
                    options=list(students_by_id),
                    format_func=lambda sid: (
                        f'{students_by_id[sid]["last_name"]} '
                        f'{students_by_id[sid]["first_name"]} '
                        f'({students_by_id[sid].get("phone") or "no phone"})'
                    ),
                    help="Type to search by last name, first name, or phone.",
                )
            else:
                st.info(f"No active {group_type} students found.")
                selected_ids = []

            # --- Buttons ---
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button(
                    "💾 Save Attendance", use_container_width=True
                )
            with col_btn2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state.show_add_attendance_form = False
                    st.rerun()

            # --- Submit ---
            if submitted:
                if class_id is None:
                    st.error("No class selected.")
                elif not selected_ids:
                    st.error("Select at least one student.")
                else:
                    saved, skipped, failed = 0, 0, []

                    for sid in selected_ids:
                        try:
                            attendance.add_attendance(
                                student_id=sid,
                                class_id=class_id,
                                attendance_date=attendance_date.isoformat(),
                                attendance_type="membership",
                            )
                            saved += 1
                        except ValueError:
                            # e.g. UNIQUE(student_id, class_id, attendance_date)
                            # already exists — treat as "already marked present"
                            skipped += 1
                        except Exception as e:
                            failed.append((sid, str(e)))

                    if failed:
                        st.error(
                            f"Saved {saved}, skipped {skipped} already-marked, "
                            f"but {len(failed)} failed."
                        )
                        for sid, msg in failed:
                            s = students_by_id.get(sid, {})
                            st.caption(
                                f"• {s.get('last_name','?')} "
                                f"{s.get('first_name','?')}: {msg}"
                            )
                    else:
                        msg = f"✅ Saved attendance for {saved} student(s)."
                        if skipped:
                            msg += f" ({skipped} already marked present.)"
                        st.success(msg)

                        st.session_state.show_add_attendance_form = False
                        st.session_state.attendance_form_counter += 1
                        st.rerun()

   
# --- Display table with row selection ---
if st.session_state.search_results is None:
    df = load_table_data(DB_PATH)
    st.markdown(f"**Total students:** {len(df):,}")
    event = st.dataframe(
    df,
    selection_mode="single-row",
    on_select="rerun",
    key="main_table"
)
# --- Capture selection ---
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
            schema=attendance.ALLOWED_ATTENDANCE_FIELDS, 
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

# --- Edit Attendance Form ---
if st.session_state.show_edit_form:
    attendance_id = st.session_state.edit_row_id
    data = st.session_state.selected_row_id  # dict with all fields

    if data is None:
        st.error("No attendance record selected. Please close and select a row.")
        st.session_state.show_edit_form = False
        st.rerun()
    else:
        # --- Load students and classes for the dropdowns ---
        try:
            students_list = students.find_students()
        except Exception as e:
            st.error(f"Could not load students: {e}")
            students_list = []

        try:
            classes_list = classes.find_classes()
        except Exception as e:
            st.error(f"Could not load classes: {e}")
            classes_list = []

        students_by_id = {s["id"]: s for s in students_list}
        classes_by_id = {c["id"]: c for c in classes_list}

        current_student_id = data.get('student_id')
        current_class_id = data.get('class_id')

        with st.container():
            st.write("### Edit Attendance")
            st.markdown("*Required fields are marked with **`*`**")

            with st.form("edit_attendance_form"):
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
                        default_student_index = student_options.index(current_student_id)

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

                # --- Class selectbox ---
                if classes_by_id:
                    class_options = list(classes_by_id.keys())
                    if current_class_id not in class_options:
                        st.warning(
                            f"Original class (id={current_class_id}) "
                            "no longer exists. Please pick another."
                        )
                        default_class_index = 0
                    else:
                        default_class_index = class_options.index(current_class_id)

                    selected_class_id = st.selectbox(
                        "Class **`*`**",
                        options=class_options,
                        index=default_class_index,
                        format_func=lambda cid: (
                            f'{classes_by_id[cid].get("schedule_day", "")} '
                            f'{classes_by_id[cid].get("start_time", "")} — '
                            f'{classes_by_id[cid].get("name", "")}'
                        ),
                    )
                else:
                    st.warning("No classes available.")
                    selected_class_id = None

                # --- Date ---
                # Stored as 'YYYY-MM-DD' (from attendance_date.isoformat()
                # at insert time), which st.date_input accepts directly.
                attendance_date = st.date_input(
                    "Date **`*`**",
                    value=data.get('attendance_date'),
                    min_value=MIN_DATE,
                    max_value=MAX_DATE,
                )

                # --- Attendance Type radio ---
                type_options = ['membership', 'single', 'debt']
                current_type = data.get('attendance_type', 'membership')
                default_type_index = (
                    type_options.index(current_type)
                    if current_type in type_options
                    else 0
                )
                attendance_type = st.radio(
                    'Attendance Type',
                    type_options,
                    horizontal=True,
                    index=default_type_index,
                )

                # --- Notes ---
                notes = st.text_area("Notes", value=data.get('notes') or '')

                # --- Buttons ---
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "💾 Update Attendance", use_container_width=True
                    )
                with col_btn2:
                    if st.form_submit_button("❌ Cancel", use_container_width=True):
                        st.session_state.show_edit_form = False
                        st.session_state.selected_row_id = None
                        st.session_state.edit_row_id = None
                        st.rerun()

                # --- Submit ---
                if submitted:
                    if selected_student_id is None:
                        st.error("Student is required.")
                    elif selected_class_id is None:
                        st.error("Class is required.")
                    elif attendance_date is None:
                        st.error("Date is required.")
                    else:
                        try:
                            updates = {
                                'student_id': selected_student_id,
                                'class_id': selected_class_id,
                                'attendance_date': attendance_date.isoformat(),
                                'attendance_type': attendance_type,
                                'notes': notes.strip() if notes else None,
                            }

                            success = attendance.update_attendance(
                                attendance_id, **updates
                            )

                            if success:
                                st.success(
                                    f"✅ Attendance {attendance_id} updated "
                                    "successfully!"
                                )
                                st.session_state.show_edit_form = False
                                st.session_state.selected_row_id = None
                                st.session_state.edit_row_id = None
                                st.rerun()
                            else:
                                st.warning(
                                    f"Attendance {attendance_id} not found. "
                                    "It may have been deleted."
                                )

                        except ValueError as e:
                            st.error(f"Validation error: {e}")
                        except Exception as e:
                            st.error(f"Database error: {e}")