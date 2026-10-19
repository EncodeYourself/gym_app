from app.database.database_ctl import get_connection
from datetime import datetime
import logging 
import sqlite3
from typing import Any, Dict, Optional, List
import re 
logger = logging.getLogger(__name__)

ALLOWED_CLASS_FILTERS = {'schedule_day', 'is_active', 'instructor_id'}
ALLOWED_CLASSES_FIELDS = {
    'name',
    'instructor_id',     
    'schedule_day',
    'start_time',
    'duration_minutes',
    'description',
    'is_active',
}
VALID_DAYS = {
    'Monday', 
    'Tuesday', 
    'Wednesday', 
    'Thursday', 
    'Friday', 
    'Saturday', 
    'Sunday'
}

DEFAULT_DURATION = 90


def add_class(
    name: str,
    instructor_id: int,
    schedule_day: str,
    start_time: str,
    duration_minutes: Optional[int] = None,
    description: Optional[str] = None,
    is_active: int = 1,
) -> int:
    """
    Insert a new class into the schedule.

    Args:
        name: Class name. Must be non-empty.
        instructor_id: Positive integer id of the trainer who teaches it.
        schedule_day: One of VALID_DAYS ('Monday' ... 'Sunday').
        start_time: Time of day in HH:MM 24-hour format (e.g. '18:00').
        duration_minutes: Length of the session. Defaults to DEFAULT_DURATION.
        description: Optional free text.
        is_active: 1 if the class is currently running, 0 otherwise.

    Returns:
        The new class id.

    Raises:
        ValueError: If any field fails validation, or instructor_id
            references a trainer that does not exist.
        RuntimeError: If the database operation fails.
    """

    # --- Validate name ---
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"name must be a non-empty string, got: {name!r}")
    name = name.strip()

    # --- Validate instructor_id ---
    if isinstance(instructor_id, bool) or not isinstance(instructor_id, int) or instructor_id <= 0:
        raise ValueError(
            f"instructor_id must be a positive integer, got: {instructor_id!r}"
        )

    # --- Validate schedule_day ---
    if schedule_day not in VALID_DAYS:
        raise ValueError(
            f"Invalid schedule_day: {schedule_day!r}. "
            f"Expected one of: {sorted(VALID_DAYS)}"
        )

    # --- Validate start_time (mirrors the schema's GLOB + range check) ---
    if not isinstance(start_time, str) or not start_time.strip():
        raise ValueError(
            f"start_time must be a non-empty string, got: {start_time!r}"
        )
    start_time = start_time.strip()
    if not re.match(r'^[0-2][0-9]:[0-5][0-9]$', start_time):
        raise ValueError(
            f"Invalid start_time: {start_time!r}. Expected HH:MM "
            f"(e.g. '09:30', '18:00')."
        )
    if start_time > '23:59':
        raise ValueError(
            f"Invalid start_time: {start_time!r}. Hours cannot exceed 23."
        )

    # --- Validate duration_minutes ---
    if duration_minutes is None:
        duration_minutes = DEFAULT_DURATION
    if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes <= 0:
        raise ValueError(
            f"duration_minutes must be a positive integer, got: {duration_minutes!r}"
        )

    # --- Validate description ---
    if description is not None:
        if not isinstance(description, str):
            raise ValueError(
                f"description must be a string or None, got: {description!r}"
            )
        description = description.strip() or None

    # --- Validate is_active ---
    if isinstance(is_active, bool) or is_active not in (0, 1):
        raise ValueError(f"is_active must be 0 or 1, got: {is_active!r}")

    # --- Build data (omit description when None so schema default applies) ---
    data: Dict[str, Any] = {
        'name': name,
        'instructor_id': instructor_id,
        'schedule_day': schedule_day,
        'start_time': start_time,
        'duration_minutes': duration_minutes,
        'is_active': is_active,
    }
    if description is not None:
        data['description'] = description

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO classes ({columns_str}) VALUES ({placeholders})"

    # --- Execute insert ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            new_id = cursor.lastrowid

        logger.info(
            "Class added: id=%s, name=%s, instructor_id=%s, schedule_day=%s, "
            "start_time=%s, duration_minutes=%s, is_active=%s",
            new_id, name, instructor_id, schedule_day,
            start_time, duration_minutes, is_active,
        )
        return new_id

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'foreign key' in msg:
            raise ValueError(
                f"instructor_id={instructor_id} references a trainer "
                f"that does not exist."
            ) from e
        raise ValueError(f"Class violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception(
            "Failed to add class: name=%s, instructor_id=%s",
            name, instructor_id,
        )
        raise RuntimeError(f"Failed to add class: {e}") from e

def delete_class(class_id):
    '''
    Delete an class by id.

    Args:
        class_id: int, x > 0

    Returns:
        True if the class was deleted, False if it did not exist.

    Raises:
        ValueError: If class_id is not a positive integer.
        RuntimeError: If the database operation fails.
    '''

    if not isinstance(class_id, int) or class_id <= 0:
        raise ValueError(f"class_id must be a positive integer, got: {class_id}")

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM classes WHERE id = ?",
                (class_id,)
            )
            

            if cursor.rowcount == 0:
                logger.warning("No class found with id=%s", class_id)
                return False

            logger.info("class deleted: id=%s", class_id)
            return True

    except Exception as e:
        logger.exception("Failed to delete class id=%s", class_id)
        raise RuntimeError(f"Failed to delete class: {e}") from e

def update_class(class_id: int, **kwargs: Any) -> bool:
    """
    Update a class record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        class_id: Positive integer id of the class to update.
        **kwargs: One or more fields to update. Allowed fields:
            name, instructor_id, schedule_day, start_time,
            duration_minutes, description, is_active

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no class was found.

    Raises:
        ValueError: If class_id is invalid, field validation fails, or
            instructor_id references a trainer that does not exist.
        RuntimeError: If the database operation fails.
    """

    # --- Validate class_id ---
    if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id <= 0:
        raise ValueError(f"class_id must be a positive integer, got: {class_id!r}")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_CLASSES_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for class update id=%s", class_id)
        return False

    # --- Validate individual fields ---
    if 'name' in updates:
        value = updates['name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"name must be a non-empty string, got: {value!r}")
        updates['name'] = value.strip()

    if 'instructor_id' in updates:
        value = updates['instructor_id']
        # instructor_id is nullable in the schema — None means "unassign".
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"instructor_id must be a positive integer or None, "
                    f"got: {value!r}"
                )

    if 'schedule_day' in updates:
        value = updates['schedule_day']
        if value not in VALID_DAYS:
            raise ValueError(
                f"Invalid schedule_day: {value!r}. "
                f"Expected one of: {sorted(VALID_DAYS)}"
            )

    if 'start_time' in updates:
        value = updates['start_time']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"start_time must be a non-empty string, got: {value!r}"
            )
        value = value.strip()
        if not re.match(r'^[0-2][0-9]:[0-5][0-9]$', value):
            raise ValueError(
                f"Invalid start_time: {value!r}. Expected HH:MM (e.g. '18:00')."
            )
        if value > '23:59':
            raise ValueError(
                f"Invalid start_time: {value!r}. Hours cannot exceed 23."
            )
        updates['start_time'] = value

    if 'duration_minutes' in updates:
        value = updates['duration_minutes']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"duration_minutes must be a positive integer, got: {value!r}"
            )

    if 'description' in updates and updates['description'] is not None:
        value = updates['description']
        if not isinstance(value, str):
            raise ValueError(
                f"description must be a string or None, got: {value!r}"
            )
        updates['description'] = value.strip() or None

    if 'is_active' in updates:
        value = updates['is_active']
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"is_active must be 0 or 1, got: {value!r}")

    # --- Execute update ---
    # updated_at is handled by the trigger on this table — no manual set.
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [class_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE classes SET {set_clause} WHERE id = ?",
                values,
            )

            if cursor.rowcount == 0:
                logger.warning("No class found with id=%s", class_id)
                return False

        # Log after context exit — commit has fired, change is durable.
        logger.info(
            "Class updated: id=%s, fields=%s",
            class_id,
            list(updates.keys()),
        )
        return True

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'foreign key' in msg:
            raise ValueError(
                f"instructor_id={updates.get('instructor_id')} references "
                f"a trainer that does not exist."
            ) from e
        raise ValueError(f"Class violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to update class id=%s", class_id)
        raise RuntimeError(f"Failed to update class: {e}") from e







def find_classes(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for classes, or list them all if no arguments are given.

    Joins trainers so callers get the instructor's name alongside the
    raw instructor_id. Classes with no assigned instructor have
    instructor_id = NULL and trainer fields all NULL.

    Supports:
        - Exact match on class id
        - Partial match on class name (case-insensitive)
        - Partial match on instructor first_name, last_name

    Filters (all optional, AND-ed with the search term):
        - schedule_day  ('Monday', 'Tuesday', ... 'Sunday')
        - is_active     (0 or 1)
        - instructor_id (exact; positive integer)

    Args:
        search_term: String to search for. If None or empty, the term
            is ignored and only filters apply.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching class records as dictionaries, each including
        trainer display fields.

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
    unknown = set(kwargs) - ALLOWED_CLASS_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    if kwargs.get('schedule_day') is not None:
        value = kwargs['schedule_day']
        if value not in VALID_DAYS:
            raise ValueError(
                f"Invalid schedule_day: {value}. "
                f"Expected one of: {sorted(VALID_DAYS)}"
            )

    if kwargs.get('is_active') is not None:
        value = kwargs['is_active']
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"is_active must be 0 or 1, got: {value!r}")

    if kwargs.get('instructor_id') is not None:
        value = kwargs['instructor_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"instructor_id must be a positive integer, got: {value!r}"
            )

    # --- Build WHERE clause dynamically (may end up empty) ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        class_id = None
        try:
            class_id = int(search_term)
        except ValueError:
            pass

        term_clauses = []
        if class_id is not None:
            term_clauses.append("c.id = ?")
            params.append(class_id)

        like = f"%{search_term}%"
        term_clauses.append("c.name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("t.first_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("t.last_name LIKE ? COLLATE NOCASE")
        params.append(like)

        where_parts.append("(" + " OR ".join(term_clauses) + ")")

    # Filter clauses: skip any that are None.
    filter_columns = {
        'schedule_day':  'c.schedule_day',
        'is_active':     'c.is_active',
        'instructor_id': 'c.instructor_id',
    }
    for field, value in kwargs.items():
        if value is None:
            continue
        where_parts.append(f"{filter_columns[field]} = ?")
        params.append(value)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
       SELECT
            c.id,
            c.name,
            c.instructor_id,
            c.schedule_day,
            c.start_time,
            c.duration_minutes,
            c.description,
            c.is_active,
            c.created_at,
            c.updated_at,
            (t.last_name || ' ' || t.first_name) AS trainer_name
        FROM classes c
        LEFT JOIN trainers t ON t.id = c.instructor_id
        {where_sql}
        ORDER BY
            CASE c.schedule_day
                WHEN 'Monday'    THEN 1
                WHEN 'Tuesday'   THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday'  THEN 4
                WHEN 'Friday'    THEN 5
                WHEN 'Saturday'  THEN 6
                WHEN 'Sunday'    THEN 7
                ELSE 99
            END,
            c.start_time
    """

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No classes found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Class search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except sqlite3.Error as e:
        logger.exception(
            "Failed to search classes: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search classes: {e}") from e