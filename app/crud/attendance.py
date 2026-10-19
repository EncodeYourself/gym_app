from app.database.database_ctl import get_connection
from datetime import datetime
import app.crud.memberships as memberships
import logging
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALLOWED_ATTENDANCE_FIELDS = {
    'student_id',
    'class_id',
    'attendance_date',
    'attendance_type',
    'notes',
    'membership_id'
    
}
ALLOWED_ATTENDANCE_FILTERS = {
    'student_id',
    'class_id',
    'membership_id',
    'attendance_type',
    'date_from',
    'date_to',
}

VALID_ATTENDANCE_TYPES = {'membership', 'single', 'debt', 'trial'}

def add_attendance(
    conn,
    student_id: int,
    class_id: int,
    attendance_date: str,
    membership_id: Optional[int] = None,
    **kwargs: Any
) -> int:
    """
    Insert a new attendance record.

    Private — takes an open connection and does not commit; the caller
    owns the transaction.

    Args:
        conn: An open sqlite3.Connection.
        student_id: Required. Positive integer id of the student.
        class_id: Required. Positive integer id of the class.
        attendance_date: Required. Date of attendance (YYYY-MM-DD).
        membership_id: Required when attendance_type='membership';
            must be None for 'single', 'debt', and 'trial'.
        **kwargs: Optional fields:
            attendance_type ('membership', 'single', 'debt', 'trial';
                default 'membership'),
            notes (free text)

    Returns:
        The new attendance id.

    Raises:
        ValueError: If required fields are missing/invalid, optional
            field validation fails, or the attendance_type/membership_id
            combination is inconsistent.
        sqlite3.IntegrityError: Propagates to the caller for translation
            (UNIQUE collision, FK violation). Not caught here.
        sqlite3.Error: Propagates for the same reason.
    """

    # --- Validate required fields ---
    if isinstance(student_id, bool) or not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(
            f"student_id must be a positive integer, got: {student_id!r}"
        )

    if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id <= 0:
        raise ValueError(
            f"class_id must be a positive integer, got: {class_id!r}"
        )

    if not isinstance(attendance_date, str) or not attendance_date.strip():
        raise ValueError(
            f"attendance_date must be a non-empty string, got: {attendance_date!r}"
        )
    try:
        datetime.strptime(attendance_date.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid attendance_date: {attendance_date!r}. Expected YYYY-MM-DD."
        )

    # --- Validate optional membership_id ---
    if membership_id is not None:
        if isinstance(membership_id, bool) or not isinstance(membership_id, int) or membership_id <= 0:
            raise ValueError(
                f"membership_id must be a positive integer or None, "
                f"got: {membership_id!r}"
            )

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_ATTENDANCE_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Validate attendance_type ---
    attendance_type = kwargs.get('attendance_type', 'membership')
    if attendance_type is None:
        attendance_type = 'membership'
    if attendance_type not in VALID_ATTENDANCE_TYPES:
        raise ValueError(
            f"Invalid attendance_type: {attendance_type}. "
            f"Expected one of: {sorted(VALID_ATTENDANCE_TYPES)}"
        )

    # --- Cross-field rule: membership_id and attendance_type must agree ---
    if attendance_type == 'membership' and membership_id is None:
        raise ValueError(
            "attendance_type='membership' requires a membership_id. "
            "Use 'single', 'debt', or 'trial' for a student with no "
            "active membership."
        )

    if attendance_type != 'membership' and membership_id is not None:
        raise ValueError(
            f"attendance_type='{attendance_type}' must not have a "
            f"membership_id (got membership_id={membership_id})."
        )

    # --- Build final field set ---
    values: Dict[str, Any] = {
        'student_id': student_id,
        'class_id': class_id,
        'attendance_date': attendance_date.strip(),
        'attendance_type': attendance_type,
    }
    if membership_id is not None:
        values['membership_id'] = membership_id

    if 'notes' in kwargs and kwargs['notes'] is not None:
        value = kwargs['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")
        stripped = value.strip()
        values['notes'] = stripped or None

    # --- Execute insert on the caller's connection ---
    placeholders = ', '.join(['?'] * len(values))
    columns_str = ', '.join(values.keys())
    query = f"INSERT INTO attendance ({columns_str}) VALUES ({placeholders})"

    cursor = conn.execute(query, list(values.values()))
    return cursor.lastrowid

def update_attendance(attendance_id: int, **kwargs: Any) -> bool:
    """
    Update an attendance record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        attendance_id: Positive integer id of the attendance record to update.
        **kwargs: One or more fields to update. Allowed fields:
            student_id, class_id, attendance_date,
            attendance_type, notes

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no attendance record was found.

    Raises:
        ValueError: If attendance_id is invalid, field validation fails,
            or the update collides with the UNIQUE constraint on
            (student_id, class_id, attendance_date).
        RuntimeError: If the database operation fails.
    """

    if not isinstance(attendance_id, int) or attendance_id <= 0:
        raise ValueError(
            f"attendance_id must be a positive integer, got: {attendance_id}"
        )

    unknown = set(kwargs) - ALLOWED_ATTENDANCE_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning(
            "No valid fields provided for attendance update id=%s", attendance_id
        )
        return False

    # --- Validate individual fields ---
    if 'student_id' in updates:
        value = updates['student_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"student_id must be a positive integer, got: {value!r}"
            )

    if 'class_id' in updates:
        value = updates['class_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"class_id must be a positive integer, got: {value!r}"
            )

    if 'attendance_date' in updates:
        value = updates['attendance_date']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"attendance_date must be a non-empty string, got: {value!r}"
            )
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid attendance_date: {value!r}. Expected YYYY-MM-DD."
            )
        updates['attendance_date'] = value.strip()

    if 'attendance_type' in updates:
        value = updates['attendance_type']
        if value not in VALID_ATTENDANCE_TYPES:
            raise ValueError(
                f"Invalid attendance_type: {value}. "
                f"Expected one of: {sorted(VALID_ATTENDANCE_TYPES)}"
            )

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")
        stripped = value.strip()
        updates['notes'] = stripped or None

    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [attendance_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE attendance SET {set_clause} WHERE id = ?",
                values,
            )
            

            if cursor.rowcount == 0:
                logger.warning("No attendance found with id=%s", attendance_id)
                return False

            logger.info(
                "Attendance updated: id=%s, fields=%s",
                attendance_id,
                list(updates.keys()),
            )
            return True

    except sqlite3.IntegrityError as e:
        # Most likely: UNIQUE(student_id, class_id, attendance_date) collision.
        # Could also be an FK violation if student_id / class_id is bad.
        msg = str(e).lower()
        if 'unique' in msg:
            raise ValueError(
                "This student is already marked present for this class on this date."
            ) from e
        if 'foreign key' in msg:
            raise ValueError(
                "student_id or class_id references a record that does not exist."
            ) from e
        raise ValueError(f"Attendance violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to update attendance id=%s", attendance_id)
        raise RuntimeError(f"Failed to update attendance: {e}") from e


def delete_attendance(attendance_id: int) -> bool:
    """
    Delete an attendance record by id.

    Args:
        attendance_id: Positive integer id of the attendance record to delete.

    Returns:
        True if the attendance record was deleted, False if the id did not exist.

    Raises:
        ValueError: If attendance_id is not a positive integer.
        RuntimeError: If the database operation fails.
    """

    if not isinstance(attendance_id, int) or attendance_id <= 0:
        raise ValueError(
            f"attendance_id must be a positive integer, got: {attendance_id}"
        )

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM attendance WHERE id = ?",
                (attendance_id,),
            )
            

            if cursor.rowcount == 0:
                logger.warning("No attendance found with id=%s", attendance_id)
                return False

            logger.info("Attendance deleted: id=%s", attendance_id)
            return True

    except sqlite3.Error as e:
        logger.exception("Failed to delete attendance id=%s", attendance_id)
        raise RuntimeError(f"Failed to delete attendance: {e}") from e

def count_attendance_in_range(start: str, end: str) -> int:
    """
    Count attendance records with attendance_date in [start, end).

    Args:
        start: ISO date string 'YYYY-MM-DD' (inclusive).
        end:   ISO date string 'YYYY-MM-DD' (exclusive).
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM attendance "
                "WHERE attendance_date >= ? AND attendance_date < ?",
                (start, end),
            ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error as e:
        logger.exception(
            "Failed to count attendance in range %s to %s", start, end
        )
        raise RuntimeError(f"Failed to count attendance: {e}") from e


def count_slipping_students(days: int = 14, as_of: Optional[str] = None) -> int:
    """
    Count active students who haven't attended in the last `days` days.

    A student with no attendance at all counts as slipping.

    Args:
        days: Lookback window in days. Default 14.
        as_of: ISO date to evaluate as of. Defaults to today.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
        raise ValueError(f"days must be a positive integer, got: {days!r}")

    if as_of is None:
        as_of = datetime.date.today().isoformat()
    cutoff = (
        datetime.date.fromisoformat(as_of) - datetime.timedelta(days=days)
    ).isoformat()

    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM students s
                WHERE s.status = 'active'
                  AND NOT EXISTS (
                      SELECT 1 FROM attendance a
                      WHERE a.student_id = s.id
                        AND a.attendance_date >= ?
                  )
                """,
                (cutoff,),
            ).fetchone()
        return row[0] if row else 0
    except sqlite3.Error as e:
        logger.exception("Failed to count slipping students")
        raise RuntimeError(f"Failed to count slipping students: {e}") from e

def record_attendance(
    student_id: int,
    class_id: int,
    attendance_date: str,
    attendance_type: str = 'membership',
    notes: Optional[str] = None,
) -> int:
    """
    Record an attendance and, for membership-type rows, consume one
    training from the student's active membership — atomically.

    For attendance_type='membership':
        - An active membership must exist, or ValueError is raised.
        - The attendance row is linked to it via membership_id.
        - used_trainings is incremented by 1.
        - If the plan is not unlimited and the new used_trainings
          reaches plan.max_trainings, the membership's status is set
          to 'completed' in the same transaction.

    For 'single', 'debt', 'trial':
        - No membership is required.
        - The attendance row's membership_id is NULL.
        - No counter or status is touched.

    All writes run on one connection with a single commit. If any step
    fails, the whole operation is rolled back — no half-written state.

    Args:
        student_id: Positive integer id of the student.
        class_id: Positive integer id of the class.
        attendance_date: Date in YYYY-MM-DD format.
        attendance_type: One of 'membership', 'single', 'debt', 'trial'.
            Defaults to 'membership'.
        notes: Optional free text.

    Returns:
        The id of the inserted attendance row.

    Raises:
        ValueError: Invalid input, no active membership (for type
            'membership'), or the student is already marked present.
        RuntimeError: Database failure.
    """

    # --- Validate inputs ---
    if isinstance(student_id, bool) or not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(f"student_id must be a positive integer, got: {student_id!r}")

    if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id <= 0:
        raise ValueError(f"class_id must be a positive integer, got: {class_id!r}")

    if not isinstance(attendance_date, str) or not attendance_date.strip():
        raise ValueError(
            f"attendance_date must be a non-empty string, got: {attendance_date!r}"
        )
    try:
        datetime.strptime(attendance_date.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid attendance_date: {attendance_date!r}. Expected YYYY-MM-DD."
        )
    attendance_date = attendance_date.strip()

    if attendance_type not in VALID_ATTENDANCE_TYPES:
        raise ValueError(
            f"Invalid attendance_type: {attendance_type}. "
            f"Expected one of: {sorted(VALID_ATTENDANCE_TYPES)}"
        )

    if notes is not None:
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string or None, got: {notes!r}")
        notes = notes.strip() or None

    # --- Resolve membership (only for type='membership') ---
    membership: Optional[Dict[str, Any]] = None

    if attendance_type == 'membership':
        membership = memberships.get_active_membership(student_id)

        if membership is None:
            raise ValueError(
                f"Student {student_id} has no active membership. "
                f"Use 'single', 'debt', or 'trial' if this is a "
                f"non-membership visit."
            )

    # --- Atomic write: one connection, one commit ---
    try:
        with get_connection() as conn:

            attendance_id = add_attendance(
                conn,
                student_id=student_id,
                class_id=class_id,
                attendance_date=attendance_date,
                attendance_type=attendance_type,
                membership_id=membership['id'] if membership else None,
                notes=notes,
            )

            if membership is not None:
                new_used = memberships._increment_used_trainings(conn, membership['id'])

                max_trainings = membership.get('plan_max_trainings')
                is_unlimited = membership.get('plan_is_unlimited')

                # Limit rule: an unlimited plan never completes by count.
                # Otherwise, reaching max_trainings flips status to 'completed'.
                if (
                    not is_unlimited
                    and max_trainings is not None
                    and new_used >= max_trainings
                ):
                    memberships._set_membership_status(conn, membership['id'], 'completed')

        logger.info(
            "Attendance recorded: id=%s, student_id=%s, class_id=%s, "
            "membership_id=%s, date=%s, type=%s",
            attendance_id,
            student_id,
            class_id,
            membership['id'] if membership else None,
            attendance_date,
            attendance_type,
        )
        return attendance_id

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'unique' in msg:
            raise ValueError(
                f"Student {student_id} is already marked present for "
                f"class {class_id} on {attendance_date}."
            ) from e
        if 'foreign key' in msg:
            raise ValueError(
                "student_id, class_id, or membership_id references a "
                "record that does not exist."
            ) from e
        raise ValueError(f"Attendance violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception(
            "Failed to record attendance: student_id=%s, class_id=%s, date=%s",
            student_id,
            class_id,
            attendance_date,
        )
        raise RuntimeError(f"Failed to record attendance: {e}") from e




def find_attendance(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for attendance records, or list them all if no arguments
    are given.

    Joins students and classes so callers get readable names alongside
    the raw FK ids.

    Supports:
        - Exact match on attendance id
        - Partial match on student first_name, last_name, phone
        - Partial match on class name

    Filters (all optional, AND-ed with the search term):
        - student_id      (exact)
        - class_id        (exact)
        - membership_id   (exact; pass 0 to mean "no membership")
        - attendance_type ('membership', 'single', 'debt', 'trial')
        - date_from       (YYYY-MM-DD, inclusive)
        - date_to         (YYYY-MM-DD, inclusive)

    Args:
        search_term: String to search for. If None or empty, the term
            is ignored and only filters apply.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of attendance records as dictionaries, each including
        student and class display fields.

    Raises:
        ValueError: If search_term is not a string/None, a filter name
            is unknown, or a filter value is invalid.
        RuntimeError: If the database operation fails.
    """

    # --- Normalize search_term ---
    if search_term is not None:
        if not isinstance(search_term, str):
            raise ValueError(
                f"search_term must be a string or None, got: {search_term!r}"
            )
        search_term = search_term.strip() or None

    # --- Detect unknown filters ---
    unknown = set(kwargs) - ALLOWED_ATTENDANCE_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    for field_name in ('student_id', 'class_id', 'membership_id'):
        if kwargs.get(field_name) is not None:
            value = kwargs[field_name]
            # membership_id also accepts 0 as "no membership"
            if field_name == 'membership_id' and value == 0:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"{field_name} must be a positive integer, got: {value!r}"
                )

    if kwargs.get('attendance_type') is not None:
        value = kwargs['attendance_type']
        if value not in VALID_ATTENDANCE_TYPES:
            raise ValueError(
                f"Invalid attendance_type: {value}. "
                f"Expected one of: {sorted(VALID_ATTENDANCE_TYPES)}"
            )

    for date_field in ('date_from', 'date_to'):
        if kwargs.get(date_field) is not None:
            value = kwargs[date_field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{date_field} must be a non-empty string, got: {value!r}"
                )
            try:
                datetime.strptime(value.strip(), "%Y-%m-%d")
            except ValueError:
                raise ValueError(
                    f"Invalid {date_field}: {value!r}. Expected YYYY-MM-DD."
                )
            kwargs[date_field] = value.strip()

    if (
        kwargs.get('date_from') is not None
        and kwargs.get('date_to') is not None
        and kwargs['date_from'] > kwargs['date_to']
    ):
        raise ValueError(
            f"date_from ({kwargs['date_from']}) cannot be after "
            f"date_to ({kwargs['date_to']})."
        )

    # --- Build WHERE clause dynamically (may end up empty) ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        attendance_id = None
        try:
            attendance_id = int(search_term)
        except ValueError:
            pass

        term_clauses = []
        if attendance_id is not None:
            term_clauses.append("a.id = ?")
            params.append(attendance_id)

        like = f"%{search_term}%"
        term_clauses.append("s.first_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("s.last_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("s.phone LIKE ?")
        params.append(like)
        term_clauses.append("c.name LIKE ? COLLATE NOCASE")
        params.append(like)

        where_parts.append("(" + " OR ".join(term_clauses) + ")")

    # Filter clauses: skip any that are None.
    filter_columns = {
        'student_id':      'a.student_id',
        'class_id':        'a.class_id',
        'membership_id':   'a.membership_id',
        'attendance_type': 'a.attendance_type',
    }
    for field, value in kwargs.items():
        if value is None:
            continue
        if field == 'date_from':
            where_parts.append("a.attendance_date >= ?")
            params.append(value)
        elif field == 'date_to':
            where_parts.append("a.attendance_date <= ?")
            params.append(value)
        elif field == 'membership_id' and value == 0:
            where_parts.append("a.membership_id IS NULL")
        else:
            where_parts.append(f"{filter_columns[field]} = ?")
            params.append(value)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT
            a.id,
            a.student_id,
            a.class_id,
            a.membership_id,
            a.attendance_date,
            a.attendance_type,
            a.notes,
            a.created_at,
            s.first_name       AS student_first_name,
            s.last_name        AS student_last_name,
            s.phone            AS student_phone,
            s.group_type       AS student_group_type,
            c.name             AS class_name,
            c.schedule_day     AS class_day,
            c.start_time       AS class_time,
            c.duration_minutes AS class_duration_minutes
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        JOIN classes  c ON c.id = a.class_id
        {where_sql}
        ORDER BY a.attendance_date DESC, a.id DESC
    """

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No attendance found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Attendance search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except sqlite3.Error as e:
        logger.exception(
            "Failed to search attendance: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search attendance: {e}") from e