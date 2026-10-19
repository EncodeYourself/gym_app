from app.database.database_ctl import get_connection
import logging 
from typing import Any, Dict, Optional, List
import sqlite3

logger = logging.getLogger(__name__)


VALID_EXPENSE_CATEGORIES = {
    'rent', 'utilities', 'cleaning', 'salary', 'equipment',
    'repairs', 'marketing', 'taxes', 'other',
}


ALLOWED_PAYEE_FIELDS = {
    'name',
    'linked_trainer_id',
    'preferred_category',
    'is_active',
    'notes',
}

ALLOWED_PAYEE_FILTERS = {
    'is_active',
    'linked_trainer_id',
    'preferred_category',
}

def add_payee(
    name: str,
    linked_trainer_id: Optional[int] = None,
    preferred_category: Optional[str] = None,
    is_active: int = 1,
    notes: Optional[str] = None,
) -> int:
    """
    Insert a new payee into the payees catalog.

    Args:
        name: Payee name. Must be non-empty. The schema enforces global
            uniqueness — two payees cannot share a name.
        linked_trainer_id: Optional. If this payee is also a trainer,
            pass their trainer id. The schema enforces at most one
            payee per trainer. Must be None for external vendors.
        preferred_category: Optional. Default expense category for this
            payee, used by the UI to pre-fill the expense form. Must be
            None or one of VALID_EXPENSE_CATEGORIES.
        is_active: 1 if the payee is currently active, 0 if archived.
        notes: Optional free text.

    Returns:
        The new payee id.

    Raises:
        ValueError: If any field fails validation, or a UNIQUE constraint
            is violated (duplicate name, or the trainer already has a
            payee record).
        RuntimeError: If the database operation fails.
    """

    # --- Validate name ---
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"name must be a non-empty string, got: {name!r}")
    name = name.strip()

    # --- Validate linked_trainer_id ---
    if linked_trainer_id is not None:
        if isinstance(linked_trainer_id, bool) or not isinstance(linked_trainer_id, int) or linked_trainer_id <= 0:
            raise ValueError(
                f"linked_trainer_id must be a positive integer or None, "
                f"got: {linked_trainer_id!r}"
            )

    # --- Validate preferred_category ---
    if preferred_category is not None:
        if preferred_category not in VALID_EXPENSE_CATEGORIES:
            raise ValueError(
                f"Invalid preferred_category: {preferred_category}. "
                f"Expected one of: {sorted(VALID_EXPENSE_CATEGORIES)}"
            )

    # --- Validate is_active ---
    if isinstance(is_active, bool) or is_active not in (0, 1):
        raise ValueError(f"is_active must be 0 or 1, got: {is_active!r}")

    # --- Normalize notes ---
    if notes is not None:
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string or None, got: {notes!r}")
        notes = notes.strip() or None

    # --- Build data (omit optional fields when None so schema defaults apply) ---
    data: Dict[str, Any] = {
        'name': name,
        'is_active': is_active,
    }
    if linked_trainer_id is not None:
        data['linked_trainer_id'] = linked_trainer_id
    if preferred_category is not None:
        data['preferred_category'] = preferred_category
    if notes is not None:
        data['notes'] = notes

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO payees ({columns_str}) VALUES ({placeholders})"

    # --- Execute insert ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            new_id = cursor.lastrowid

        logger.info(
            "Payee added: id=%s, name=%s, linked_trainer_id=%s, "
            "preferred_category=%s, is_active=%s",
            new_id, name, linked_trainer_id, preferred_category, is_active,
        )
        return new_id

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'unique' in msg and 'name' in msg:
            raise ValueError(
                f"A payee named '{name}' already exists."
            ) from e
        if 'unique' in msg and 'linked_trainer' in msg:
            raise ValueError(
                f"Trainer {linked_trainer_id} already has a payee record. "
                f"Edit the existing one instead."
            ) from e
        if 'foreign key' in msg:
            raise ValueError(
                f"linked_trainer_id={linked_trainer_id} references a "
                f"trainer that does not exist."
            ) from e
        raise ValueError(f"Payee violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to add payee: name=%s", name)
        raise RuntimeError(f"Failed to add payee: {e}") from e


def update_payee(payee_id: int, **kwargs: Any) -> bool:
    """
    Update a payee record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        payee_id: Positive integer id of the payee to update.
        **kwargs: One or more fields to update. Allowed fields:
            name, linked_trainer_id, preferred_category, is_active, notes

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no payee was found.

    Raises:
        ValueError: If payee_id is invalid, field validation fails, or
            a UNIQUE constraint is violated (duplicate name, or the
            trainer already has a different payee record).
        RuntimeError: If the database operation fails.
    """

    if isinstance(payee_id, bool) or not isinstance(payee_id, int) or payee_id <= 0:
        raise ValueError(
            f"payee_id must be a positive integer, got: {payee_id!r}"
        )

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_PAYEE_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for payee update id=%s", payee_id)
        return False

    # --- Validate individual fields ---
    if 'name' in updates:
        value = updates['name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"name must be a non-empty string, got: {value!r}")
        updates['name'] = value.strip()

    if 'linked_trainer_id' in updates and updates['linked_trainer_id'] is not None:
        value = updates['linked_trainer_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"linked_trainer_id must be a positive integer or None, "
                f"got: {value!r}"
            )

    if 'preferred_category' in updates and updates['preferred_category'] is not None:
        value = updates['preferred_category']
        if value not in VALID_EXPENSE_CATEGORIES:
            raise ValueError(
                f"Invalid preferred_category: {value}. "
                f"Expected one of: {sorted(VALID_EXPENSE_CATEGORIES)}"
            )

    if 'is_active' in updates:
        value = updates['is_active']
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"is_active must be 0 or 1, got: {value!r}")

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")
        updates['notes'] = value.strip() or None

    # --- Execute update ---
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [payee_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE payees SET {set_clause} WHERE id = ?",
                values,
            )

            if cursor.rowcount == 0:
                logger.warning("No payee found with id=%s", payee_id)
                return False

        # Log after context exit — commit has fired, change is durable.
        logger.info(
            "Payee updated: id=%s, fields=%s",
            payee_id,
            list(updates.keys()),
        )
        return True

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'unique' in msg and 'name' in msg:
            raise ValueError(
                f"A payee named '{updates.get('name')}' already exists."
            ) from e
        if 'unique' in msg and 'linked_trainer' in msg:
            raise ValueError(
                f"Trainer {updates.get('linked_trainer_id')} already has "
                f"a different payee record."
            ) from e
        if 'foreign key' in msg:
            raise ValueError(
                f"linked_trainer_id={updates.get('linked_trainer_id')} "
                f"references a trainer that does not exist."
            ) from e
        raise ValueError(f"Payee violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to update payee id=%s", payee_id)
        raise RuntimeError(f"Failed to update payee: {e}") from e

def delete_payee(payee_id: int) -> bool:
    """
    Delete a payee by id.

    Intended for correcting mistakes (duplicate rows, typo'd entries).
    To retire a payee that has received money, deactivate it with
    update_payee(payee_id, is_active=0) instead — that hides it from
    new expenses while preserving the payee for historical references.

    A payee that is referenced by any expense cannot be deleted
    (ON DELETE RESTRICT). The reference must be cleared first — either
    by deleting the expenses that use this payee, or by deactivating
    the payee instead.

    Args:
        payee_id: Positive integer id of the payee to delete.

    Returns:
        True if the payee was deleted, False if the id did not exist.

    Raises:
        ValueError: If payee_id is not a positive integer, or the payee
            is referenced by at least one expense.
        RuntimeError: If the database operation fails.
    """

    if isinstance(payee_id, bool) or not isinstance(payee_id, int) or payee_id <= 0:
        raise ValueError(
            f"payee_id must be a positive integer, got: {payee_id!r}"
        )

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM payees WHERE id = ?",
                (payee_id,),
            )

            if cursor.rowcount == 0:
                logger.warning("No payee found with id=%s", payee_id)
                return False

        # Commit has fired on context exit. Log only after durability.
        logger.info("Payee deleted: id=%s", payee_id)
        return True

    except sqlite3.IntegrityError as e:
        # FK violation from expenses.payee_id.
        logger.warning(
            "Cannot delete payee id=%s: referenced by expenses", payee_id
        )
        raise ValueError(
            "This payee has recorded expenses and cannot be deleted. "
            "Deactivate it instead."
        ) from e

    except sqlite3.Error as e:
        logger.exception("Failed to delete payee id=%s", payee_id)
        raise RuntimeError(f"Failed to delete payee: {e}") from e

def find_payees(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for payees, or list them all if no arguments are given.

    Joins trainers when the payee is linked to one, so callers get the
    trainer's name alongside the raw FK id. External vendors have
    linked_trainer_id = NULL and trainer fields all NULL.

    Each returned row includes an `expense_count` field: how many
    expense rows reference this payee. That's what the delete form
    uses to decide whether to offer a delete button at all.

    Supports:
        - Exact match on payee id
        - Partial match on payee name (case-insensitive)
        - Partial match on trainer first_name, last_name when linked

    Filters (all optional, AND-ed with the search term):
        - is_active          (0 or 1)
        - linked_trainer_id  (exact; positive integer)
        - preferred_category (one of VALID_EXPENSE_CATEGORIES)

    Args:
        search_term: String to search for. If None or empty, the term
            is ignored and only filters apply.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching payee records as dictionaries.

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
    unknown = set(kwargs) - ALLOWED_PAYEE_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    if kwargs.get('is_active') is not None:
        value = kwargs['is_active']
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"is_active must be 0 or 1, got: {value!r}")

    if kwargs.get('linked_trainer_id') is not None:
        value = kwargs['linked_trainer_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"linked_trainer_id must be a positive integer, got: {value!r}"
            )

    if kwargs.get('preferred_category') is not None:
        value = kwargs['preferred_category']
        if value not in VALID_EXPENSE_CATEGORIES:
            raise ValueError(
                f"Invalid preferred_category: {value}. "
                f"Expected one of: {sorted(VALID_EXPENSE_CATEGORIES)}"
            )

    # --- Build WHERE clause dynamically (may end up empty) ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        payee_id = None
        try:
            payee_id = int(search_term)
        except ValueError:
            pass

        term_clauses = []
        if payee_id is not None:
            term_clauses.append("p.id = ?")
            params.append(payee_id)

        like = f"%{search_term}%"
        term_clauses.append("p.name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("t.first_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("t.last_name LIKE ? COLLATE NOCASE")
        params.append(like)

        where_parts.append("(" + " OR ".join(term_clauses) + ")")

    # Filter clauses: skip any that are None.
    filter_columns = {
        'is_active':          'p.is_active',
        'linked_trainer_id':  'p.linked_trainer_id',
        'preferred_category': 'p.preferred_category',
    }
    for field, value in kwargs.items():
        if value is None:
            continue
        where_parts.append(f"{filter_columns[field]} = ?")
        params.append(value)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT
            p.id,
            p.name,
            p.linked_trainer_id,
            p.preferred_category,
            p.is_active,
            p.notes,
            p.created_at,
            p.updated_at,
            t.first_name AS trainer_first_name,
            t.last_name  AS trainer_last_name,
            (
                SELECT COUNT(*)
                FROM expenses e
                WHERE e.payee_id = p.id
            ) AS expense_count
        FROM payees p
        LEFT JOIN trainers t ON t.id = p.linked_trainer_id
        {where_sql}
        ORDER BY p.is_active DESC, p.name
    """

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No payees found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Payee search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except sqlite3.Error as e:
        logger.exception(
            "Failed to search payees: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search payees: {e}") from e