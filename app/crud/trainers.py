from app.database.database_ctl import get_connection
from datetime import datetime
import logging
import sqlite3
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

ALLOWED_TRAINER_FIELDS = {
    'first_name',
    'last_name',
    'phone',
    'telegram_handle',
    'role',
    'specialties',
    'pay_type',
    'pay_rate',
    'notes',
    'status',
}

VALID_ROLES = {'coach', 'admin', 'other'}
VALID_PAY_TYPES = {'hourly', 'per_class', 'per_session', 'salary', 'volunteer'}
VALID_STATUS = {'active', 'inactive'}

def add_trainer(
    first_name: str,
    last_name: str,
    phone: str,
    **kwargs: Any
) -> int | None:
    """
    Insert a new trainer record.

    Args:
        first_name: Required. Trainer's first name.
        last_name: Required. Trainer's last name.
        phone: Required. Trainer's phone number.
        **kwargs: Optional fields:
            telegram_handle,
            role ('coach', 'assistant', 'cutman', 'admin', 'other'),
            specialties (free text),
            pay_type ('hourly', 'per_class', 'per_session', 'salary', 'volunteer', 'other'),
            pay_rate (non-negative int),
            notes,
            status ('active', 'inactive')

    Returns:
        The new trainer id.

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
    unknown = set(kwargs) - ALLOWED_TRAINER_FIELDS
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
    if 'telegram_handle' in updates and updates['telegram_handle'] is not None:
        value = updates['telegram_handle']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"telegram_handle must be a non-empty string, got: {value!r}"
            )

    if 'role' in updates and updates['role'] is not None:
        value = updates['role']
        if value not in VALID_ROLES:
            raise ValueError(
                f"Invalid role: {value}. Expected one of: {sorted(VALID_ROLES)}"
            )

    if 'specialties' in updates and updates['specialties'] is not None:
        value = updates['specialties']
        if not isinstance(value, str):
            raise ValueError(f"specialties must be a string or None, got: {value!r}")

    if 'pay_type' in updates and updates['pay_type'] is not None:
        value = updates['pay_type']
        if value not in VALID_PAY_TYPES:
            raise ValueError(
                f"Invalid pay_type: {value}. Expected one of: {sorted(VALID_PAY_TYPES)}"
            )

    if 'pay_rate' in updates and updates['pay_rate'] is not None:
        value = updates['pay_rate']
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"pay_rate must be a non-negative integer or None, got: {value!r}"
            )

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")

    if 'status' in updates and updates['status'] is not None:
        value = updates['status']
        if value not in VALID_STATUS:
            raise ValueError(
                f"Invalid status: {value}. Expected one of: {sorted(VALID_STATUS)}"
            )

    # --- Execute insert ---
    placeholders = ', '.join(['?'] * len(updates))
    columns_str = ', '.join(updates.keys())
    query = f"INSERT INTO trainers ({columns_str}) VALUES ({placeholders})"

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(updates.values()))
            conn.commit()
            new_id = cursor.lastrowid

        logger.info(
            "Trainer added: id=%s, first_name=%s, last_name=%s",
            new_id,
            first_name,
            last_name,
        )
        return new_id

    except Exception as e:
        logger.exception("Failed to add trainer: %s %s", first_name, last_name)
        raise RuntimeError(f"Failed to add trainer: {e}") from e

def update_trainer(trainer_id: int, **kwargs: Any) -> bool:
    """
    Update a trainer record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        trainer_id: Positive integer id of the trainer to update.
        **kwargs: One or more fields to update. Allowed fields:
            first_name, last_name, phone, telegram_handle,
            role, specialties, pay_type, pay_rate, notes, status

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no trainer was found.

    Raises:
        ValueError: If trainer_id is invalid or field validation fails.
        RuntimeError: If the database operation fails.
    """

    if not isinstance(trainer_id, int) or trainer_id <= 0:
        raise ValueError(f"trainer_id must be a positive integer, got: {trainer_id}")

    unknown = set(kwargs) - ALLOWED_TRAINER_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for trainer update id=%s", trainer_id)
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

    if 'role' in updates and updates['role'] is not None:
        value = updates['role']
        if value not in VALID_ROLES:
            raise ValueError(
                f"Invalid role: {value}. Expected one of: {sorted(VALID_ROLES)}"
            )

    if 'specialties' in updates and updates['specialties'] is not None:
        value = updates['specialties']
        if not isinstance(value, str):
            raise ValueError(f"specialties must be a string or None, got: {value!r}")

    if 'pay_type' in updates and updates['pay_type'] is not None:
        value = updates['pay_type']
        if value not in VALID_PAY_TYPES:
            raise ValueError(
                f"Invalid pay_type: {value}. Expected one of: {sorted(VALID_PAY_TYPES)}"
            )

    if 'pay_rate' in updates and updates['pay_rate'] is not None:
        value = updates['pay_rate']
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"pay_rate must be a non-negative integer or None, got: {value!r}"
            )

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")

    if 'status' in updates:
        value = updates['status']
        if value not in VALID_STATUS:
            raise ValueError(
                f"Invalid status: {value}. Expected one of: {sorted(VALID_STATUS)}"
            )

    # --- Build SET clause; always bump updated_at ---
    set_parts = [f"{key} = ?" for key in updates.keys()]
    set_parts.append("updated_at = datetime('now', 'localtime')")
    set_clause = ", ".join(set_parts)
    values = list(updates.values()) + [trainer_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE trainers SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No trainer found with id=%s", trainer_id)
                return False

            logger.info(
                "Trainer updated: id=%s, fields=%s",
                trainer_id,
                list(updates.keys()),
            )
            return True

    except Exception as e:
        logger.exception("Failed to update trainer id=%s", trainer_id)
        raise RuntimeError(f"Failed to update trainer: {e}") from e

def delete_trainer(trainer_id: int) -> bool:
    """
    Delete a trainer by id.

    Intended for correcting mistakes (duplicate entries, typo'd rows).
    For trainers who have taught classes or been involved in substitutions,
    prefer update_trainer(trainer_id, status='inactive') to preserve history.

    Raises:
        ValueError: If trainer_id is invalid, or the trainer is referenced
            by other records (substitutions, classes, etc.).
        RuntimeError: If the database operation fails.
    """

    if not isinstance(trainer_id, int) or trainer_id <= 0:
        raise ValueError(f"trainer_id must be a positive integer, got: {trainer_id}")

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM trainers WHERE id = ?",
                (trainer_id,)
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No trainer found with id=%s", trainer_id)
                return False

            logger.info("Trainer deleted: id=%s", trainer_id)
            return True

    except sqlite3.IntegrityError as e:
        logger.warning("Cannot delete trainer id=%s: referenced by other records", trainer_id)
        raise ValueError(
            f"Trainer {trainer_id} has associated records and cannot be deleted. "
            f"Mark them inactive instead."
        ) from e

    except sqlite3.Error as e:
        logger.exception("Failed to delete trainer id=%s", trainer_id)
        raise RuntimeError(f"Failed to delete trainer: {e}") from e

def search_trainers(search_term: str) -> List[Dict[str, Any]]:
    """
    Search for trainers by id, first name, or last name.

    Supports:
        - Exact match on trainer id
        - Partial match on first name (case-insensitive)
        - Partial match on last name (case-insensitive)
        - Partial match on phone (case-insensitive)

    Args:
        search_term: String to search for. Can be a numeric id or a name.

    Returns:
        List of matching trainer records as dictionaries.

    Raises:
        ValueError: If search_term is empty or invalid.
        RuntimeError: If the database operation fails.
    """

    if not isinstance(search_term, str) or not search_term.strip():
        raise ValueError(f"search_term must be a non-empty string, got: {search_term!r}")

    search_term = search_term.strip()

    trainer_id = None
    try:
        trainer_id = int(search_term)
    except ValueError:
        pass

    query = """
        SELECT
            id,
            last_name,
            first_name,
            phone,
            telegram_handle,
            role,
            specialties,
            pay_type,
            pay_rate,
            notes,
            status,
            created_at,
            updated_at
        FROM trainers
        WHERE (? IS NOT NULL AND id = ?)
           OR first_name LIKE ? COLLATE NOCASE
           OR last_name LIKE ? COLLATE NOCASE
           OR phone LIKE ?
        ORDER BY last_name, first_name
        LIMIT 50
    """

    params = (
        trainer_id,
        trainer_id,
        f"%{search_term}%",
        f"%{search_term}%",
        f"%{search_term}%",
    )

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info("No trainers found for search term: %s", search_term)
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Trainer search: term=%s, results=%d",
                search_term,
                len(results),
            )
            return results

    except Exception as e:
        logger.exception("Failed to search trainers with term=%s", search_term)
        raise RuntimeError(f"Failed to search trainers: {e}") from e