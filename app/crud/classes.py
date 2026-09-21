from app.database.database_ctl import get_connection
from datetime import datetime
import logging 
import sqlite3
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

ALLOWED_CLASSES_FIELDS = {
    'name', 
    'instructor', 
    'schedule_day', 
    'start_time', 
    'duration_minutes', 
    'description', 
    'is_active'
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
    instructor: str, 
    schedule_day: str, 
    start_time: str, 
    duration_minutes: Optional[int]=None, 
    description: Optional[str]=None, 
    is_active: int=1):

    if not duration_minutes:
        duration_minutes = DEFAULT_DURATION
    
    data = {
        'name' : name,
        'instructor' : instructor,
        'schedule_day' : schedule_day,
        'start_time' : start_time, 
        'duration_minutes' : duration_minutes,
        'description' : description,
        'is_active' : is_active
    }

    if description is None:
        data.pop('description')
    
    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO classes ({columns_str}) VALUES ({placeholders})"
    
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            conn.commit()
            new_id = cursor.lastrowid

        logger.info(
            '''Class added: name=%s, instructor=%s, schedule_day=%s, 
            start_time=%s, duration_minutes=%s, description=%s, is_active=%s''',
            name, instructor, schedule_day, start_time, 
            duration_minutes, description, is_active
        )
        return new_id

    except Exception as e:
        logger.exception('''Failed to add class for name=%s, instructor=%s, schedule_day=%s, 
            start_time=%s, duration_minutes=%s, description=%s, is_active=%s''', 
            name, instructor, schedule_day, start_time, 
            duration_minutes, description, is_active)
        raise RuntimeError(f'Failed to add class: {e}') from e


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
            conn.commit()

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

    Only allowed fields can be updated.

    Args:
        class_id: Positive integer id of the class to update.
        **kwargs: One or more fields to update. Allowed fields:
            name, instructor, schedule_day, start_time,
            duration_minutes, description, is_active

    Returns:
        True if the update was successful, False if no valid fields were
        provided or no class was found.

    Raises:
        ValueError: If class_id is invalid or field validation fails.
        RuntimeError: If the database operation fails.
    """

    # --- Validate class_id ---
    if not isinstance(class_id, int) or class_id <= 0:
        raise ValueError(f"class_id must be a positive integer, got: {class_id}")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_CLASSES_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Build updates ---
    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for class update id=%s", class_id)
        return False

    # --- Validate individual fields ---
    if 'name' in updates:
        if not isinstance(updates['name'], str) or not updates['name'].strip():
            raise ValueError(f"name must be a non-empty string, got: {updates['name']!r}")

    if 'instructor' in updates:
        if not isinstance(updates['instructor'], str) or not updates['instructor'].strip():
            raise ValueError(
                f"instructor must be a non-empty string, got: {updates['instructor']!r}"
            )

    if 'schedule_day' in updates:
        if updates['schedule_day'] not in VALID_DAYS:
            raise ValueError(
                f"Invalid schedule_day: {updates['schedule_day']}. "
                f"Expected one of: {sorted(VALID_DAYS)}"
            )

    if 'start_time' in updates:
        try:
            datetime.strptime(updates['start_time'], "%H:%M")
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid start_time: {updates['start_time']}. Expected HH:MM format."
            )

    if 'duration_minutes' in updates:
        duration = updates['duration_minutes']
        if not isinstance(duration, int) or duration <= 0:
            raise ValueError(
                f"duration_minutes must be a positive integer, got: {duration}"
            )

    if 'is_active' in updates:
        if updates['is_active'] not in (0, 1):
            raise ValueError(
                f"is_active must be 0 or 1, got: {updates['is_active']}"
            )

    if 'description' in updates and updates['description'] is not None:
        if not isinstance(updates['description'], str):
            raise ValueError(
                f"description must be a string or None, got: {updates['description']!r}"
            )

    # --- Execute update ---
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [class_id]

    try:
        with get_connection() as conn:
            # Add updated_at to the SET clause
            set_parts = [f"{field} = ?" for field in updates.keys()]
            set_parts.append("updated_at = datetime('now', 'localtime')")
            set_clause = ", ".join(set_parts)

            # Add the timestamp value to the parameters
            values = list(updates.values()) + [class_id]
            cursor = conn.execute(
                f"UPDATE classes SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No class found with id=%s", class_id)
                return False

            logger.info(
                "Class updated: id=%s, fields=%s",
                class_id,
                list(updates.keys()),
            )
            return True

    except Exception as e:
        logger.exception("Failed to update class id=%s", class_id)
        raise RuntimeError(f"Failed to update class: {e}") from e
ALLOWED_CLASS_FILTERS = {'schedule_day', 'is_active'}


def find_classes(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for classes, or list them all if no arguments are given.

    Supports:
        - Exact match on class id
        - Partial match on class name (case-insensitive)
        - Partial match on instructor (case-insensitive)

    Filters (all optional, AND-ed with the search term):
        - schedule_day ('Monday', 'Tuesday', ... 'Sunday')
        - is_active (0 or 1)

    Args:
        search_term: String to search for. Can be a numeric id,
            class name, or instructor name. If None or empty, the
            term is ignored.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching class records as dictionaries. If no search_term
        and no filters are provided, returns all classes.

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
            raise ValueError(
                f"is_active must be 0 or 1, got: {value!r}"
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
            term_clauses.append("id = ?")
            params.append(class_id)
        like = f"%{search_term}%"
        term_clauses.append("name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("instructor LIKE ? COLLATE NOCASE")
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
            name,
            instructor,
            schedule_day,
            start_time,
            duration_minutes,
            description,
            is_active,
            created_at
        FROM classes
        {where_sql}
        ORDER BY schedule_day, start_time
    """

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
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

    except Exception as e:
        logger.exception(
            "Failed to search classes: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search classes: {e}") from e