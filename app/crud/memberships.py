from app.database.database_ctl import get_connection
from datetime import datetime
import logging 
import sqlite3
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

ALLOWED_MEMBERSHIP_FIELDS = {
    'student_id',
    'plan_id',
    'start_date',
    'expiry_date',
    'used_trainings',
    'status',
    'upgraded_from',
    'notes',
}
VALID_MEMBERSHIP_STATUSES = {
    'active', 'on_hold', 'expired', 'completed', 'cancelled', 'upgraded',
}

ALLOWED_MEMBERSHIP_FILTERS = {'student_id', 'plan_id', 'status'}

def add_membership(
    student_id: int,
    plan_id: int,
    start_date: str,
    expiry_date: str,
    used_trainings: int = 0,
    status: str = 'active',
    upgraded_from: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Insert a new membership record.

    Args:
        student_id: Required. Positive integer id of the student.
        plan_id: Required. Positive integer id of the plan.
        start_date: Required. YYYY-MM-DD.
        expiry_date: Required. YYYY-MM-DD.
        used_trainings: Non-negative integer. Defaults to 0.
        status: One of VALID_MEMBERSHIP_STATUSES. Defaults to 'active'.
        upgraded_from: Optional membership id this row supersedes.
        notes: Optional free text.

    Returns:
        The new membership id.

    Raises:
        ValueError: If any field is invalid, or the dates are malformed,
            or expiry_date is before start_date.
        RuntimeError: If the database operation fails.
    """

    # --- Validate required fields ---
    if isinstance(student_id, bool) or not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(f"student_id must be a positive integer, got: {student_id!r}")

    if isinstance(plan_id, bool) or not isinstance(plan_id, int) or plan_id <= 0:
        raise ValueError(f"plan_id must be a positive integer, got: {plan_id!r}")

    for field_name, value in (("start_date", start_date), ("expiry_date", expiry_date)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string, got: {value!r}")
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid {field_name}: {value!r}. Expected YYYY-MM-DD."
            )

    start_date = start_date.strip()
    expiry_date = expiry_date.strip()

    if datetime.strptime(expiry_date, "%Y-%m-%d") < datetime.strptime(start_date, "%Y-%m-%d"):
        raise ValueError(
            f"expiry_date ({expiry_date}) cannot be before "
            f"start_date ({start_date})."
        )

    # --- Validate optional fields ---
    if isinstance(used_trainings, bool) or not isinstance(used_trainings, int) or used_trainings < 0:
        raise ValueError(
            f"used_trainings must be a non-negative integer, got: {used_trainings!r}"
        )

    if status not in VALID_MEMBERSHIP_STATUSES:
        raise ValueError(
            f"Invalid status: {status}. "
            f"Expected one of: {sorted(VALID_MEMBERSHIP_STATUSES)}"
        )

    if upgraded_from is not None:
        if isinstance(upgraded_from, bool) or not isinstance(upgraded_from, int) or upgraded_from <= 0:
            raise ValueError(
                f"upgraded_from must be a positive integer or None, got: {upgraded_from!r}"
            )

    if notes is not None:
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string or None, got: {notes!r}")
        notes = notes.strip() or None

    # --- Build data dict ---
    data = {
        'student_id': student_id,
        'plan_id': plan_id,
        'start_date': start_date,
        'expiry_date': expiry_date,
        'used_trainings': used_trainings,
        'status': status,
    }
    if upgraded_from is not None:
        data['upgraded_from'] = upgraded_from
    if notes is not None:
        data['notes'] = notes

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO memberships ({columns_str}) VALUES ({placeholders})"

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            
            new_id = cursor.lastrowid

        logger.info(
            "Membership added: id=%s, student_id=%s, plan_id=%s, "
            "start=%s, expiry=%s, status=%s",
            new_id, student_id, plan_id, start_date, expiry_date, status,
        )
        return new_id

    except sqlite3.IntegrityError as e:
        # FK violation (bad student_id / plan_id), UNIQUE(upgraded_from),
        # or a CHECK failure the app layer missed.
        raise ValueError(f"Membership violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception(
            "Failed to add membership: student_id=%s, plan_id=%s",
            student_id, plan_id,
        )
        raise RuntimeError(f"Failed to add membership: {e}") from e

def update_membership(membership_id: int, **kwargs: Any) -> bool:
    """
    Update a membership record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        membership_id: Positive integer id of the membership to update.
        **kwargs: One or more fields to update. Allowed fields:
            student_id, plan_id, start_date, expiry_date,
            used_trainings, status, upgraded_from, notes

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no membership was found.

    Raises:
        ValueError: If membership_id is invalid, field validation fails,
            or the update would make upgraded_from point at itself.
        RuntimeError: If the database operation fails.
    """

    if isinstance(membership_id, bool) or not isinstance(membership_id, int) or membership_id <= 0:
        raise ValueError(
            f"membership_id must be a positive integer, got: {membership_id!r}"
        )

    unknown = set(kwargs) - ALLOWED_MEMBERSHIP_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning(
            "No valid fields provided for membership update id=%s", membership_id
        )
        return False

    # --- Validate individual fields ---
    if 'student_id' in updates:
        value = updates['student_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"student_id must be a positive integer, got: {value!r}"
            )

    if 'plan_id' in updates:
        value = updates['plan_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"plan_id must be a positive integer, got: {value!r}"
            )

    if 'start_date' in updates:
        value = updates['start_date']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"start_date must be a non-empty string, got: {value!r}"
            )
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid start_date: {value!r}. Expected YYYY-MM-DD."
            )
        updates['start_date'] = value.strip()

    if 'expiry_date' in updates:
        value = updates['expiry_date']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"expiry_date must be a non-empty string, got: {value!r}"
            )
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid expiry_date: {value!r}. Expected YYYY-MM-DD."
            )
        updates['expiry_date'] = value.strip()

    if 'used_trainings' in updates:
        value = updates['used_trainings']
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"used_trainings must be a non-negative integer, got: {value!r}"
            )

    if 'status' in updates:
        value = updates['status']
        if value not in VALID_MEMBERSHIP_STATUSES:
            raise ValueError(
                f"Invalid status: {value}. "
                f"Expected one of: {sorted(VALID_MEMBERSHIP_STATUSES)}"
            )

    if 'upgraded_from' in updates and updates['upgraded_from'] is not None:
        value = updates['upgraded_from']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"upgraded_from must be a positive integer or None, got: {value!r}"
            )

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")
        updates['notes'] = value.strip() or None

    # --- Cross-field guard: upgraded_from must not point at this row ---
    if 'upgraded_from' in updates and updates['upgraded_from'] == membership_id:
        raise ValueError(
            f"upgraded_from cannot point at the membership itself "
            f"(id={membership_id})."
        )

    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [membership_id]

    try:
        with get_connection() as conn:
            # --- Guard: merged start_date / expiry_date must still be sane ---
            # Only needed if the update touches either date and might
            # leave expiry before start.
            if 'start_date' in updates or 'expiry_date' in updates:
                row = conn.execute(
                    "SELECT start_date, expiry_date FROM memberships WHERE id = ?",
                    (membership_id,),
                ).fetchone()

                if row is None:
                    logger.warning(
                        "No membership found with id=%s", membership_id
                    )
                    return False

                merged_start = updates.get('start_date', row[0])
                merged_expiry = updates.get('expiry_date', row[1])

                if (
                    datetime.strptime(merged_expiry, "%Y-%m-%d")
                    < datetime.strptime(merged_start, "%Y-%m-%d")
                ):
                    raise ValueError(
                        f"expiry_date ({merged_expiry}) cannot be before "
                        f"start_date ({merged_start})."
                    )

            cursor = conn.execute(
                f"UPDATE memberships SET {set_clause} WHERE id = ?",
                values,
            )
            

            if cursor.rowcount == 0:
                logger.warning(
                    "No membership found with id=%s", membership_id
                )
                return False

            logger.info(
                "Membership updated: id=%s, fields=%s",
                membership_id,
                list(updates.keys()),
            )
            return True

    except sqlite3.IntegrityError as e:
        # UNIQUE(upgraded_from), FK violation, or a CHECK that fired.
        msg = str(e).lower()
        if 'unique' in msg and 'upgraded_from' in msg:
            raise ValueError(
                "Another membership already points to this one as its successor."
            ) from e
        if 'foreign key' in msg:
            raise ValueError(
                "student_id, plan_id, or upgraded_from references a "
                "record that does not exist."
            ) from e
        raise ValueError(f"Membership violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to update membership id=%s", membership_id)
        raise RuntimeError(f"Failed to update membership: {e}") from e

def delete_membership(membership_id: int) -> bool:
    """
    Delete a membership record by id.

    Intended for correcting mistakes (wrong student, wrong plan, duplicate
    row). To end a membership cleanly, use update_membership to set
    status='cancelled' instead — that preserves the row for history.

    Two foreign-key side effects are possible:

    - If another membership has upgraded_from pointing at this row, that
      successor's upgraded_from is set to NULL (ON DELETE SET NULL). The
      successor row survives; only the chain link is broken.

    - If any payment references this membership, the delete is refused
      (ON DELETE RESTRICT) and ValueError is raised. Payments are the
      only table that blocks deletion; attendance and credit entries use
      SET NULL and will be unlinked automatically.

    Args:
        membership_id: Positive integer id of the membership to delete.

    Returns:
        True if the membership was deleted, False if the id did not exist.

    Raises:
        ValueError: If membership_id is not a positive integer, or the
            membership is referenced by at least one payment.
        RuntimeError: If the database operation fails.
    """

    if isinstance(membership_id, bool) or not isinstance(membership_id, int) or membership_id <= 0:
        raise ValueError(
            f"membership_id must be a positive integer, got: {membership_id!r}"
        )

    try:
        with get_connection() as conn:
            # --- Check for a successor before deleting ---
            # ON DELETE SET NULL would handle this silently, but a
            # warning in the log is cheap and makes the side effect
            # visible if it ever surprises someone.
            successor = conn.execute(
                "SELECT id FROM memberships WHERE upgraded_from = ?",
                (membership_id,),
            ).fetchone()

            if successor is not None:
                logger.warning(
                    "Deleting membership id=%s, which is the predecessor "
                    "of membership id=%s. The successor's upgraded_from "
                    "will be set to NULL.",
                    membership_id,
                    successor["id"],
                )

            cursor = conn.execute(
                "DELETE FROM memberships WHERE id = ?",
                (membership_id,),
            )

            if cursor.rowcount == 0:
                logger.warning("No membership found with id=%s", membership_id)
                return False

        # Commit fired on context exit. Log only after durability.
        logger.info("Membership deleted: id=%s", membership_id)
        return True

    except sqlite3.IntegrityError as e:
        # Payments.membership_id is ON DELETE RESTRICT — any payment
        # linked to this membership blocks the delete.
        logger.warning(
            "Cannot delete membership id=%s: referenced by payments",
            membership_id,
        )
        raise ValueError(
            "This membership is referenced by at least one payment and "
            "cannot be deleted. To end it, use update_membership with "
            "status='cancelled'."
        ) from e

    except sqlite3.Error as e:
        logger.exception("Failed to delete membership id=%s", membership_id)
        raise RuntimeError(f"Failed to delete membership: {e}") from e


def find_membership(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for memberships, or list them all if no arguments are given.

    Joins students and plans so callers get readable names alongside
    the raw FK ids.

    Supports:
        - Exact match on membership_id
        - Partial match on student first_name, last_name, phone
        - Partial match on plan name

    Filters (all optional, AND-ed with the search term):
        - student_id (exact)
        - plan_id (exact)
        - status ('active', 'on_hold', 'expired', 'completed',
                  'cancelled', 'upgraded')

    Args:
        search_term: String to search for. If None or empty, the term
            is ignored and only filters apply.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching membership records as dictionaries, each
        including student and plan display fields.

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
    unknown = set(kwargs) - ALLOWED_MEMBERSHIP_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    if kwargs.get('student_id') is not None:
        value = kwargs['student_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"student_id must be a positive integer, got: {value!r}"
            )

    if kwargs.get('plan_id') is not None:
        value = kwargs['plan_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"plan_id must be a positive integer, got: {value!r}"
            )

    if kwargs.get('status') is not None:
        value = kwargs['status']
        if value not in VALID_MEMBERSHIP_STATUSES:
            raise ValueError(
                f"Invalid status: {value}. "
                f"Expected one of: {sorted(VALID_MEMBERSHIP_STATUSES)}"
            )

    # --- Build WHERE clause dynamically ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        membership_id = None
        try:
            membership_id = int(search_term)
        except ValueError:
            pass

        term_clauses = []
        if membership_id is not None:
            term_clauses.append("m.id = ?")
            params.append(membership_id)

        like = f"%{search_term}%"
        term_clauses.append("s.first_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("s.last_name LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("s.phone LIKE ?")
        params.append(like)
        term_clauses.append("p.name LIKE ? COLLATE NOCASE")
        params.append(like)

        where_parts.append("(" + " OR ".join(term_clauses) + ")")

    # Filter clauses: skip any that are None.
    # All filters map to a qualified column name.
    filter_columns = {
        'student_id': 'm.student_id',
        'plan_id':    'm.plan_id',
        'status':     'm.status',
    }
    for field, value in kwargs.items():
        if value is None:
            continue
        where_parts.append(f"{filter_columns[field]} = ?")
        params.append(value)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT
            m.id,
            m.student_id,
            m.plan_id,
            m.start_date,
            m.expiry_date,
            m.used_trainings,
            m.status,
            m.upgraded_from,
            m.notes,
            m.created_at,
            m.updated_at,
            s.first_name      AS student_first_name,
            s.last_name       AS student_last_name,
            s.phone           AS student_phone,
            s.group_type      AS student_group_type,
            p.name            AS plan_name,
            p.price           AS plan_price,
            p.duration_weeks  AS plan_duration_weeks,
            p.max_trainings   AS plan_max_trainings,
            p.is_unlimited    AS plan_is_unlimited,
            p.is_single       AS plan_is_single
        FROM memberships m
        JOIN students s ON s.id = m.student_id
        JOIN plans    p ON p.id = m.plan_id
        {where_sql}
        ORDER BY m.start_date DESC, m.id DESC
    """

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No memberships found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Membership search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except Exception as e:
        logger.exception(
            "Failed to search memberships: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search memberships: {e}") from e

def get_active_membership(student_id: int) -> Optional[Dict[str, Any]]:
    """
    Return the student's currently active membership, or None.

    A membership is considered active when its status is 'active'.
    At most one such row per student is expected; if the database
    contains more (due to a race, a manual edit, or a bug elsewhere),
    the most recently started one is returned and a warning is logged.

    Args:
        student_id: Positive integer id of the student.

    Returns:
        A dict with the membership row, or None if the student has no
        active membership.

    Raises:
        ValueError: If student_id is not a positive integer.
        RuntimeError: If the database operation fails.
    """

    if isinstance(student_id, bool) or not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(
            f"student_id must be a positive integer, got: {student_id!r}"
        )

    query = '''
    SELECT
    m.id, m.student_id, m.plan_id, m.start_date, m.expiry_date,
    m.used_trainings, m.status, m.upgraded_from, m.notes,
    m.created_at, m.updated_at,
    p.max_trainings   AS plan_max_trainings,
    p.is_unlimited    AS plan_is_unlimited
    FROM memberships m
    JOIN plans p ON p.id = m.plan_id
    WHERE m.student_id = ? AND m.status = 'active'
    ORDER BY m.start_date DESC, m.id DESC
    '''

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, (student_id,))
            rows = cursor.fetchall()

            if not rows:
                return None

            if len(rows) > 1:
                # Not expected: the workflow enforces one active per student.
                # If this fires, something upstream let a second one through.
                logger.warning(
                    "Student %s has %d active memberships (ids: %s); "
                    "returning the most recent.",
                    student_id,
                    len(rows),
                    [row['id'] for row in rows],
                )

            return dict(rows[0])

    except sqlite3.Error as e:
        logger.exception(
            "Failed to fetch active membership for student_id=%s", student_id
        )
        raise RuntimeError(
            f"Failed to fetch active membership: {e}"
        ) from e


def _increment_used_trainings(conn, membership_id: int) -> int:
    """
    Increment a membership's used_trainings by 1.

    Private — takes an open connection and does not commit; the caller
    owns the transaction.

    Args:
        conn: An open sqlite3.Connection.
        membership_id: Positive integer id of the membership.

    Returns:
        The membership's used_trainings after the increment.

    Raises:
        ValueError: If membership_id is not a positive integer, or the
            membership does not exist.
    """

    if isinstance(membership_id, bool) or not isinstance(membership_id, int) or membership_id <= 0:
        raise ValueError(
            f"membership_id must be a positive integer, got: {membership_id!r}"
        )

    cursor = conn.execute(
        "UPDATE memberships "
        "SET used_trainings = used_trainings + 1 "
        "WHERE id = ?",
        (membership_id,),
    )

    if cursor.rowcount == 0:
        raise ValueError(f"Membership {membership_id} not found.")

    row = conn.execute(
        "SELECT used_trainings FROM memberships WHERE id = ?",
        (membership_id,),
    ).fetchone()

    return row[0]

def _set_membership_status(conn, membership_id: int, status: str) -> None:
    """
    Set a membership's status. Private — takes an open connection and
    does not commit; the caller owns the transaction.

    Args:
        conn: An open sqlite3.Connection.
        membership_id: Positive integer id of the membership.
        status: One of VALID_MEMBERSHIP_STATUSES.

    Raises:
        ValueError: If membership_id or status is invalid, or the
            membership does not exist.
    """

    if isinstance(membership_id, bool) or not isinstance(membership_id, int) or membership_id <= 0:
        raise ValueError(
            f"membership_id must be a positive integer, got: {membership_id!r}"
        )

    if status not in VALID_MEMBERSHIP_STATUSES:
        raise ValueError(
            f"Invalid status: {status}. "
            f"Expected one of: {sorted(VALID_MEMBERSHIP_STATUSES)}"
        )

    cursor = conn.execute(
        "UPDATE memberships SET status = ? WHERE id = ?",
        (status, membership_id),
    )

    if cursor.rowcount == 0:
        raise ValueError(f"Membership {membership_id} not found.")