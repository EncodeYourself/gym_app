from app.database.database_ctl import get_connection
from datetime import datetime
import logging
import sqlite3
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

ALLOWED_SUBSTITUTION_FIELDS = {
    'class_id',
    'original_trainer_id',
    'substitute_trainer_id',
    'date',
    'reason'
}

def add_substitution(
    class_id: int,
    original_trainer_id: int,
    substitute_trainer_id: int,
    date: str,
    **kwargs: Any
) -> int | None:
    """
    Insert a new substitution record.

    Args:
        class_id: Required. Positive integer id of the class that was substituted.
        original_trainer_id: Required. Positive integer id of the trainer
            who was supposed to teach.
        substitute_trainer_id: Required. Positive integer id of the trainer
            who actually taught.
        date: Required. Date of the substitution (YYYY-MM-DD).
        **kwargs: Optional fields:
            reason (free text)

    Returns:
        The new substitution id.

    Raises:
        ValueError: If required fields are missing/invalid or optional
            field validation fails, or the two trainers are the same.
        RuntimeError: If the database operation fails.
    """

    # --- Validate required fields ---
    if isinstance(class_id, bool) or not isinstance(class_id, int) or class_id <= 0:
        raise ValueError(f"class_id must be a positive integer, got: {class_id!r}")

    if isinstance(original_trainer_id, bool) or not isinstance(original_trainer_id, int) or original_trainer_id <= 0:
        raise ValueError(
            f"original_trainer_id must be a positive integer, got: {original_trainer_id!r}"
        )

    if isinstance(substitute_trainer_id, bool) or not isinstance(substitute_trainer_id, int) or substitute_trainer_id <= 0:
        raise ValueError(
            f"substitute_trainer_id must be a positive integer, got: {substitute_trainer_id!r}"
        )

    if original_trainer_id == substitute_trainer_id:
        raise ValueError(
            f"original_trainer_id and substitute_trainer_id must differ, "
            f"both are {original_trainer_id}"
        )

    if not isinstance(date, str) or not date.strip():
        raise ValueError(f"date must be a non-empty string, got: {date!r}")

    try:
        datetime.strptime(date.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date: {date!r}. Expected YYYY-MM-DD.")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_SUBSTITUTION_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Build final field set ---
    values: Dict[str, Any] = {
        'class_id': class_id,
        'original_trainer_id': original_trainer_id,
        'substitute_trainer_id': substitute_trainer_id,
        'date': date.strip(),
    }
    values.update(kwargs)

    # --- Validate optional fields ---
    if 'reason' in values and values['reason'] is not None:
        value = values['reason']
        if not isinstance(value, str):
            raise ValueError(f"reason must be a string or None, got: {value!r}")
        # Normalize empty/whitespace-only to None so it doesn't clutter the log
        stripped = value.strip()
        values['reason'] = stripped or None

    # --- Execute insert ---
    placeholders = ', '.join(['?'] * len(values))
    columns_str = ', '.join(values.keys())
    query = f"INSERT INTO substitutions ({columns_str}) VALUES ({placeholders})"

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(values.values()))
            
            new_id = cursor.lastrowid

        logger.info(
            "Substitution added: id=%s, class_id=%s, original=%s, substitute=%s, date=%s",
            new_id,
            class_id,
            original_trainer_id,
            substitute_trainer_id,
            date,
        )
        return new_id

    except sqlite3.IntegrityError as e:
        # FK violation (bad class_id or trainer ids) or CHECK failure
        raise ValueError(f"Substitution violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception(
            "Failed to add substitution: class_id=%s, original=%s, substitute=%s",
            class_id,
            original_trainer_id,
            substitute_trainer_id,
        )
        raise RuntimeError(f"Failed to add substitution: {e}") from e

def update_substitution(substitution_id: int, **kwargs: Any) -> bool:
    """
    Update a substitution record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        substitution_id: Positive integer id of the substitution to update.
        **kwargs: One or more fields to update. Allowed fields:
            class_id, original_trainer_id, substitute_trainer_id,
            date, reason

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no substitution was found.

    Raises:
        ValueError: If substitution_id is invalid, field validation fails,
            or the update would make original_trainer_id and
            substitute_trainer_id identical.
        RuntimeError: If the database operation fails.
    """

    if not isinstance(substitution_id, int) or substitution_id <= 0:
        raise ValueError(
            f"substitution_id must be a positive integer, got: {substitution_id}"
        )

    unknown = set(kwargs) - ALLOWED_SUBSTITUTION_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning(
            "No valid fields provided for substitution update id=%s", substitution_id
        )
        return False

    # --- Validate individual fields ---
    if 'class_id' in updates:
        value = updates['class_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"class_id must be a positive integer, got: {value!r}"
            )

    if 'original_trainer_id' in updates:
        value = updates['original_trainer_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"original_trainer_id must be a positive integer, got: {value!r}"
            )

    if 'substitute_trainer_id' in updates:
        value = updates['substitute_trainer_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"substitute_trainer_id must be a positive integer, got: {value!r}"
            )

    if 'date' in updates:
        value = updates['date']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"date must be a non-empty string, got: {value!r}")
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date: {value!r}. Expected YYYY-MM-DD.")
        updates['date'] = value.strip()

    if 'reason' in updates and updates['reason'] is not None:
        value = updates['reason']
        if not isinstance(value, str):
            raise ValueError(f"reason must be a string or None, got: {value!r}")
        stripped = value.strip()
        updates['reason'] = stripped or None

    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [substitution_id]

    try:
        with get_connection() as conn:
            # --- Guard against collapsing original == substitute ---
            # Only needed if the update touches either trainer field.
            if 'original_trainer_id' in updates or 'substitute_trainer_id' in updates:
                row = conn.execute(
                    "SELECT original_trainer_id, substitute_trainer_id "
                    "FROM substitutions WHERE id = ?",
                    (substitution_id,),
                ).fetchone()

                if row is None:
                    logger.warning("No substitution found with id=%s", substitution_id)
                    return False

                original = updates.get('original_trainer_id', row[0])
                substitute = updates.get('substitute_trainer_id', row[1])

                if original == substitute:
                    raise ValueError(
                        f"original_trainer_id and substitute_trainer_id must differ, "
                        f"both would be {original}"
                    )

            cursor = conn.execute(
                f"UPDATE substitutions SET {set_clause} WHERE id = ?",
                values,
            )
            

            if cursor.rowcount == 0:
                logger.warning("No substitution found with id=%s", substitution_id)
                return False

            logger.info(
                "Substitution updated: id=%s, fields=%s",
                substitution_id,
                list(updates.keys()),
            )
            return True

    except sqlite3.IntegrityError as e:
        raise ValueError(f"Substitution violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to update substitution id=%s", substitution_id)
        raise RuntimeError(f"Failed to update substitution: {e}") from e

def delete_substitution(substitution_id: int) -> bool:
    """
    Delete a substitution record by id.

    Args:
        substitution_id: Positive integer id of the substitution to delete.

    Returns:
        True if the substitution was deleted, False if the id did not exist.

    Raises:
        ValueError: If substitution_id is not a positive integer.
        RuntimeError: If the database operation fails.
    """

    if not isinstance(substitution_id, int) or substitution_id <= 0:
        raise ValueError(
            f"substitution_id must be a positive integer, got: {substitution_id}"
        )

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM substitutions WHERE id = ?",
                (substitution_id,),
            )
            

            if cursor.rowcount == 0:
                logger.warning("No substitution found with id=%s", substitution_id)
                return False

            logger.info("Substitution deleted: id=%s", substitution_id)
            return True

    except sqlite3.Error as e:
        logger.exception("Failed to delete substitution id=%s", substitution_id)
        raise RuntimeError(f"Failed to delete substitution: {e}") from e