from app.database.database_ctl import get_connection
from datetime import datetime
import logging
import sqlite3
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)
ALLOWED_STUDENT_FIELDS = {
    'first_name',
    'last_name',
    'date_of_birth',
    'phone',
    'telegram_handle',
    'address',
    'emergency_contact_phone',
    'emergency_contact_name',
    'group_type',
    'comment',
    'status',
}
ALLOWED_FILTERS = {'group_type', 'status'}
VALID_GROUPS = {'adult', 'child'}
VALID_STATUS = {'active', 'inactive', 'suspended'}

def add_student(
    first_name: str,
    last_name: str,
    phone: str,
    **kwargs: Any
) -> int | None:
    """
    Insert a new student record.

    Args:
        first_name: Required. Student's first name.
        last_name: Required. Student's last name.
        phone: Required. Student's phone number.
        **kwargs: Optional fields:
            date_of_birth (YYYY-MM-DD),
            telegram_handle,
            address,
            emergency_contact_phone,
            emergency_contact_name,
            group_type ('adult' or 'child'),
            comment,
            status ('active', 'inactive', 'suspended')

    Returns:
        The new student id.

    Raises:
        ValueError: If required fields are missing/invalid or optional
            field validation fails.
        RuntimeError: If the database operation fails.
    """

    # --- Validate required fields ---
    if not isinstance(first_name, str) or not first_name.strip():
        raise ValueError(f"first_name must be a non-empty string, got: {first_name!r}")

    if not isinstance(last_name, str) or not last_name.strip():
        raise ValueError(f"last_name must be a non-empty string, got: {last_name!r}")

    if not isinstance(phone, str) or not phone.strip():
        raise ValueError(f"phone must be a non-empty string, got: {phone!r}")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_STUDENT_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Build final field set ---
    updates: Dict[str, Any] = {
        'first_name': first_name.strip(),
        'last_name': last_name.strip(),
        'phone': phone.strip(),
    }
    updates.update(kwargs)

    # --- Validate optional fields ---
    if 'date_of_birth' in updates and updates['date_of_birth'] is not None:
        value = updates['date_of_birth']
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid date_of_birth: {value}. Expected YYYY-MM-DD."
            )

    if 'telegram_handle' in updates and updates['telegram_handle'] is not None:
        value = updates['telegram_handle']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"telegram_handle must be a non-empty string, got: {value!r}"
            )

    if 'address' in updates and updates['address'] is not None:
        value = updates['address']
        if not isinstance(value, str):
            raise ValueError(f"address must be a string or None, got: {value!r}")

    if 'emergency_contact_phone' in updates and updates['emergency_contact_phone'] is not None:
        value = updates['emergency_contact_phone']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"emergency_contact_phone must be a non-empty string, got: {value!r}"
            )

    if 'emergency_contact_name' in updates and updates['emergency_contact_name'] is not None:
        value = updates['emergency_contact_name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"emergency_contact_name must be a non-empty string, got: {value!r}"
            )

    if 'group_type' in updates and updates['group_type'] is not None:
        value = updates['group_type']
        if value not in VALID_GROUPS:
            raise ValueError(
                f"Invalid group_type: {value}. Expected one of: {sorted(VALID_GROUPS)}"
            )

    if 'comment' in updates and updates['comment'] is not None:
        value = updates['comment']
        if not isinstance(value, str):
            raise ValueError(f"comment must be a string or None, got: {value!r}")

    if 'status' in updates and updates['status'] is not None:
        value = updates['status']
        if value not in VALID_STATUS:
            raise ValueError(
                f"Invalid status: {value}. Expected one of: {sorted(VALID_STATUS)}"
            )

    # --- Execute insert ---
    placeholders = ', '.join(['?'] * len(updates))
    columns_str = ', '.join(updates.keys())
    query = f"INSERT INTO students ({columns_str}) VALUES ({placeholders})"

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(updates.values()))
            conn.commit()
            new_id = cursor.lastrowid

        logger.info(
            "Student added: id=%s, first_name=%s, last_name=%s",
            new_id,
            first_name,
            last_name,
        )
        return new_id

    except Exception as e:
        logger.exception("Failed to add student: %s %s", first_name, last_name)
        raise RuntimeError(f"Failed to add student: {e}") from e

def update_student(student_id: int, **kwargs: Any) -> bool:
    """
    Update a student record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        student_id: Positive integer id of the student to update.
        **kwargs: One or more fields to update. Allowed fields:
            first_name, last_name, date_of_birth, phone,
            telegram_handle, address, emergency_contact_phone,
            emergency_contact_name, group_type, comment, status

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no student was found.

    Raises:
        ValueError: If student_id is invalid or field validation fails.
        RuntimeError: If the database operation fails.
    """

    
    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(f"student_id must be a positive integer, got: {student_id}")

    unknown = set(kwargs) - ALLOWED_STUDENT_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    
    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for student update id=%s", student_id)
        return False

    # --- Validate individual fields ---
    if 'first_name' in updates:
        value = updates['first_name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"first_name must be a non-empty string, got: {value!r}")

    if 'last_name' in updates:
        value = updates['last_name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"last_name must be a non-empty string, got: {value!r}")

    if 'date_of_birth' in updates and updates['date_of_birth'] is not None:
        value = updates['date_of_birth']
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid date_of_birth: {value}. Expected YYYY-MM-DD."
            )

    if 'phone' in updates and updates['phone'] is not None:
        value = updates['phone']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"phone must be a non-empty string, got: {value!r}")

    if 'telegram_handle' in updates and updates['telegram_handle'] is not None:
        value = updates['telegram_handle']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"telegram_handle must be a non-empty string, got: {value!r}"
            )

    if 'address' in updates and updates['address'] is not None:
        value = updates['address']
        if not isinstance(value, str):
            raise ValueError(f"address must be a string or None, got: {value!r}")

    if 'emergency_contact_phone' in updates and updates['emergency_contact_phone'] is not None:
        value = updates['emergency_contact_phone']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"emergency_contact_phone must be a non-empty string, got: {value!r}"
            )

    if 'emergency_contact_name' in updates and updates['emergency_contact_name'] is not None:
        value = updates['emergency_contact_name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"emergency_contact_name must be a non-empty string, got: {value!r}"
            )

    if 'group_type' in updates and updates['group_type'] is not None:
        value = updates['group_type']
        if value not in VALID_GROUPS:
            raise ValueError(
                f"Invalid group_type: {value}. Expected one of: {sorted(VALID_GROUPS)}"
            )

    if 'comment' in updates and updates['comment'] is not None:
        value = updates['comment']
        if not isinstance(value, str):
            raise ValueError(f"comment must be a string or None, got: {value!r}")

    if 'status' in updates:
        value = updates['status']
        if value not in VALID_STATUS:
            raise ValueError(
                f"Invalid status: {value}. Expected one of: {sorted(VALID_STATUS)}"
            )

    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [student_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE students SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No student found with id=%s", student_id)
                return False

            logger.info(
                "Student updated: id=%s, fields=%s",
                student_id,
                list(updates.keys()),
            )
            return True

    except Exception as e:
        logger.exception("Failed to update student id=%s", student_id)
        raise RuntimeError(f"Failed to update student: {e}") from e

def delete_student(student_id):
    '''
    Delete an student by id.

    Args:
        student_id: int, x > 0

    Returns:
        True if the student was deleted, False if the id did not exist.

    Raises:
        ValueError: If student_id is not a positive integer.
        RuntimeError: If the database operation fails.
    '''

    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(f"student_id must be a positive integer, got: {student_id}")

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM students WHERE id = ?",
                (student_id,)
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No student found with id=%s", student_id)
                return False

            logger.info("student deleted: id=%s", student_id)
            return True

    except Exception as e:
        logger.exception("Failed to delete student id=%s", student_id)
        raise RuntimeError(f"Failed to delete student: {e}") from e


def find_students(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for students, or list them all if no arguments are given.

    Supports:
        - Exact match on student id
        - Partial match on first name (case-insensitive)
        - Partial match on last name (case-insensitive)

    Filters (all optional, AND-ed with the search term):
        - group_type ('adult' or 'child')
        - status ('active', 'inactive', 'suspended')

    Args:
        search_term: String to search for. Can be a numeric id or a name.
            If None or empty, the term is ignored.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching student records as dictionaries. If no search_term
        and no filters are provided, returns all students.

    Raises:
        ValueError: If search_term is not a string/None, a filter name is
            unknown, or a filter value is invalid.
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
    unknown = set(kwargs) - ALLOWED_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    if kwargs.get('group_type') is not None:
        value = kwargs['group_type']
        if value not in VALID_GROUPS:
            raise ValueError(
                f"Invalid group_type: {value}. Expected one of: {sorted(VALID_GROUPS)}"
            )

    if kwargs.get('status') is not None:
        value = kwargs['status']
        if value not in VALID_STATUS:
            raise ValueError(
                f"Invalid status: {value}. Expected one of: {sorted(VALID_STATUS)}"
            )

    # --- Build WHERE clause dynamically (may end up empty) ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        student_id = None
        try:
            student_id = int(search_term)
        except ValueError:
            pass

        term_clauses = []
        if student_id is not None:
            term_clauses.append("id = ?")
            params.append(student_id)
        like = f"%{search_term}%"
        term_clauses.append("first_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("last_name LIKE ? COLLATE NOCASE")
        params.append(like)
        where_parts.append("(" + " OR ".join(term_clauses) + ")")

    # Filter clauses: skip any that are None.
    for field, value in kwargs.items():
        if value is None:
            continue
        where_parts.append(f"{field} = ?")
        params.append(value)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT
            id,
            last_name,
            first_name,
            date_of_birth,
            phone,
            telegram_handle,
            address,
            emergency_contact_phone,
            emergency_contact_name,
            group_type,
            comment,
            status,
            created_at
        FROM students
        {where_sql}
        ORDER BY last_name, first_name
    """

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No students found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Student search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except Exception as e:
        logger.exception(
            "Failed to search students: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search students: {e}") from e