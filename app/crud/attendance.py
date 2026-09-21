from app.database.database_ctl import get_connection
from datetime import datetime
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
}


VALID_ATTENDANCE_TYPES = {'membership', 'single', 'debt', 'trial'}


def add_attendance(
    student_id: int,
    class_id: int,
    attendance_date: str,
    **kwargs: Any
) -> int | None:
    """
    Insert a new attendance record.

    Args:
        student_id: Required. Positive integer id of the student.
        class_id: Required. Positive integer id of the class.
        attendance_date: Required. Date of attendance (YYYY-MM-DD).
        **kwargs: Optional fields:
            attendance_type ('membership', 'single', 'debt'; default 'membership'),
            notes (free text)

    Returns:
        The new attendance id.

    Raises:
        ValueError: If required fields are missing/invalid, optional
            field validation fails, or the record already exists
            (UNIQUE student_id + class_id + attendance_date).
        RuntimeError: If the database operation fails.
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

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_ATTENDANCE_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Build final field set ---
    values: Dict[str, Any] = {
        'student_id': student_id,
        'class_id': class_id,
        'attendance_date': attendance_date.strip(),
    }
    values.update(kwargs)

    # --- Validate optional fields ---
    if 'attendance_type' in values and values['attendance_type'] is not None:
        value = values['attendance_type']
        if value not in VALID_ATTENDANCE_TYPES:
            raise ValueError(
                f"Invalid attendance_type: {value}. "
                f"Expected one of: {sorted(VALID_ATTENDANCE_TYPES)}"
            )

    if 'notes' in values and values['notes'] is not None:
        value = values['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")
        # Normalize empty/whitespace-only to None so it doesn't clutter the log
        stripped = value.strip()
        values['notes'] = stripped or None

    # --- Execute insert ---
    placeholders = ', '.join(['?'] * len(values))
    columns_str = ', '.join(values.keys())
    query = f"INSERT INTO attendance ({columns_str}) VALUES ({placeholders})"

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(values.values()))
            conn.commit()
            new_id = cursor.lastrowid

        logger.info(
            "Attendance added: id=%s, student_id=%s, class_id=%s, date=%s, type=%s",
            new_id,
            student_id,
            class_id,
            attendance_date,
            values.get('attendance_type', 'membership'),
        )
        return new_id

    except sqlite3.IntegrityError as e:
        # Could be:
        #   - FK violation (student_id or class_id doesn't exist)
        #   - UNIQUE(student_id, class_id, attendance_date) already exists
        #   - CHECK violation on attendance_type (unlikely, we validated above)
        raise ValueError(f"Attendance violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception(
            "Failed to add attendance: student_id=%s, class_id=%s, date=%s",
            student_id,
            class_id,
            attendance_date,
        )
        raise RuntimeError(f"Failed to add attendance: {e}") from e

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
            conn.commit()

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
            conn.commit()

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