from app.database.database_ctl import get_connection
import logging 
from typing import Any, Dict, Optional, List
import sqlite3

logger = logging.getLogger(__name__)

ALLOWED_PLAN_FIELDS = {
    'name', 
    'price', 
    'duration_weeks', 
    'max_trainings', 
    'is_unlimited', 
    'is_single', 
    'is_active'
}
ALLOWED_PLAN_FILTERS = {'is_active', 'is_single', 'is_unlimited'}

def add_plan(
    name: str,
    price: int,
    duration_weeks: Optional[int],
    max_trainings: Optional[int],
    is_unlimited: int = 0,
    is_single: int = 0,
    is_active: int = 1,
) -> int | None:
    """
    Insert a new plan into the plans catalog.

    Args:
        name: Plan name. Must be unique and non-empty.
        price: Price in rubles. Must be a positive integer.
        duration_weeks: Duration in weeks.
            - Required for monthly plans (e.g., 4).
            - Must be None for single training plans.
        max_trainings: Total number of trainings allowed.
            - Required for limited plans (e.g., 8 for 2/week, 12 for 3/week).
            - Must be None for unlimited plans.
        is_unlimited: 1 if the plan has no training limit, otherwise 0.
        is_single: 1 if the plan is a single drop-in training, otherwise 0.
        is_active: 1 if the plan is currently offered, 0 if hidden.

    Returns:
        The new plan id.

    Raises:
        ValueError: If any field fails validation or business rules are violated.
        RuntimeError: If the database operation fails.
    """

    # --- Validate name ---
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"name must be a non-empty string, got: {name!r}")

    name = name.strip()

    # --- Validate price ---
    if not isinstance(price, int) or price <= 0:
        raise ValueError(f"price must be a positive integer, got: {price}")

    # --- Validate flags ---
    if is_unlimited not in (0, 1):
        raise ValueError(f"is_unlimited must be 0 or 1, got: {is_unlimited}")

    if is_single not in (0, 1):
        raise ValueError(f"is_single must be 0 or 1, got: {is_single}")

    if is_active not in (0, 1):
        raise ValueError(f"is_active must be 0 or 1, got: {is_active}")

    # --- Business rule validation ---
    if is_single == 1:
        # Single training must not have duration
        if duration_weeks is not None:
            raise ValueError(
                f"Single training plan must have duration_weeks=None, "
                f"got: {duration_weeks}"
            )
        # Single training must have exactly 1 training
        if max_trainings != 1:
            raise ValueError(
                f"Single training plan must have max_trainings=1, "
                f"got: {max_trainings}"
            )
        # Single training cannot be unlimited
        if is_unlimited == 1:
            raise ValueError("Single training plan cannot be unlimited")

    else:
        # Monthly plan must have a duration
        if duration_weeks is None or not isinstance(duration_weeks, int) or duration_weeks <= 0:
            raise ValueError(
                f"Monthly plan requires duration_weeks as a positive integer, "
                f"got: {duration_weeks!r}"
            )

        if is_unlimited == 0:
            # Limited monthly plan must have max_trainings
            if max_trainings is None or not isinstance(max_trainings, int) or max_trainings <= 0:
                raise ValueError(
                    f"Limited plan requires max_trainings as a positive integer, "
                    f"got: {max_trainings!r}"
                )
        else:
            # Unlimited plan must not have max_trainings
            if max_trainings is not None:
                raise ValueError(
                    f"Unlimited plan must have max_trainings=None, "
                    f"got: {max_trainings}"
                )

    # --- Build data ---
    data = {
        'name': name,
        'price': price,
        'duration_weeks': duration_weeks,
        'max_trainings': max_trainings,
        'is_unlimited': is_unlimited,
        'is_single': is_single,
        'is_active': is_active,
    }

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO plans ({columns_str}) VALUES ({placeholders})"

    # --- Execute insert ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            
            new_id = cursor.lastrowid

        logger.info(
            "Plan added: id=%s, name=%s, price=%s, duration_weeks=%s, "
            "max_trainings=%s, is_unlimited=%s, is_single=%s, is_active=%s",
            new_id,
            name,
            price,
            duration_weeks,
            max_trainings,
            is_unlimited,
            is_single,
            is_active,
        )
        return new_id

    except Exception as e:
        logger.exception(
            "Failed to add plan: name=%s, price=%s",
            name,
            price,
        )
        raise RuntimeError(f"Failed to add plan: {e}") from e

def update_plan(plan_id: int, **kwargs: Any) -> bool:
    """
    Update a plan record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        plan_id: Positive integer id of the plan to update.
        **kwargs: One or more fields to update. Allowed fields:
            name, price, duration_weeks, max_trainings,
            is_unlimited, is_single, is_active

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no plan was found.

    Raises:
        ValueError: If plan_id is invalid or field validation fails.
        RuntimeError: If the database operation fails.
    """

    # --- Validate plan_id ---
    if not isinstance(plan_id, int) or plan_id <= 0:
        raise ValueError(f"plan_id must be a positive integer, got: {plan_id}")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_PLAN_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Build updates ---
    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for plan update id=%s", plan_id)
        return False

    # --- Validate individual fields ---
    if 'name' in updates:
        value = updates['name']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"name must be a non-empty string, got: {value!r}")
        updates['name'] = value.strip()

    if 'price' in updates:
        value = updates['price']
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"price must be a positive integer, got: {value}")

    if 'duration_weeks' in updates and updates['duration_weeks'] is not None:
        value = updates['duration_weeks']
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"duration_weeks must be a positive integer or None, got: {value}"
            )

    if 'max_trainings' in updates and updates['max_trainings'] is not None:
        value = updates['max_trainings']
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"max_trainings must be a positive integer or None, got: {value}"
            )

    if 'is_unlimited' in updates:
        value = updates['is_unlimited']
        if value not in (0, 1):
            raise ValueError(f"is_unlimited must be 0 or 1, got: {value}")

    if 'is_single' in updates:
        value = updates['is_single']
        if value not in (0, 1):
            raise ValueError(f"is_single must be 0 or 1, got: {value}")

    if 'is_active' in updates:
        value = updates['is_active']
        if value not in (0, 1):
            raise ValueError(f"is_active must be 0 or 1, got: {value}")

    # --- Validate business rules ---
    # Need to check the resulting state if is_single or is_unlimited is being changed
    # For simplicity, we validate the fields provided.
    # Full cross-field validation would require fetching the current plan.
    # That is better done at the application level before calling this function.

    # --- Execute update ---
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [plan_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE plans SET {set_clause} WHERE id = ?",
                values
            )
            

            if cursor.rowcount == 0:
                logger.warning("No plan found with id=%s", plan_id)
                return False

            logger.info(
                "Plan updated: id=%s, fields=%s",
                plan_id,
                list(updates.keys()),
            )
            return True

    except Exception as e:
        logger.exception("Failed to update plan id=%s", plan_id)
        raise RuntimeError(f"Failed to update plan: {e}") from e

def delete_plan(plan_id: int) -> bool:
    """
    Delete a plan by id.

    Intended for correcting mistakes (duplicate rows, typo'd entries).
    To retire a plan that has been used, deactivate it with
    update_plan(plan_id, is_active=0) instead — that hides it from new
    memberships while preserving the plan for historical references.

    A plan that is referenced by any membership cannot be deleted
    (ON DELETE RESTRICT). The FK must be cleared first — either by
    deleting the memberships that use this plan, or by deactivating
    the plan instead.

    Args:
        plan_id: Positive integer id of the plan to delete.

    Returns:
        True if the plan was deleted, False if the id did not exist.

    Raises:
        ValueError: If plan_id is not a positive integer, or the plan
            is referenced by at least one membership.
        RuntimeError: If the database operation fails.
    """

    if isinstance(plan_id, bool) or not isinstance(plan_id, int) or plan_id <= 0:
        raise ValueError(
            f"plan_id must be a positive integer, got: {plan_id!r}"
        )

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM plans WHERE id = ?",
                (plan_id,),
            )
            

            if cursor.rowcount == 0:
                logger.warning("No plan found with id=%s", plan_id)
                return False

        logger.info("Plan deleted: id=%s", plan_id)
        return True

    except sqlite3.IntegrityError as e:
        # FK violation from memberships.plan_id.
        logger.warning(
            "Cannot delete plan id=%s: referenced by memberships", plan_id
        )
        raise ValueError(
            "This plan has been used in memberships and cannot be deleted. "
            "Deactivate it instead."
        ) from e

    except sqlite3.Error as e:
        logger.exception("Failed to delete plan id=%s", plan_id)
        raise RuntimeError(f"Failed to delete plan: {e}") from e

def find_plans(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for plans, or list them all if no arguments are given.

    Each returned row includes a `membership_count` field: how many
    membership rows reference this plan. That's what the delete form
    uses to decide whether to offer a delete button at all.

    Supports:
        - Exact match on plan id
        - Partial match on plan name (case-insensitive)

    Filters (all optional, AND-ed with the search term):
        - is_active     (0 or 1)
        - is_single     (0 or 1)
        - is_unlimited  (0 or 1)

    Args:
        search_term: String to search for. If None or empty, the term
            is ignored and only filters apply.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching plan records as dictionaries.

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
    unknown = set(kwargs) - ALLOWED_PLAN_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    for flag in ('is_active', 'is_single', 'is_unlimited'):
        if kwargs.get(flag) is not None:
            value = kwargs[flag]
            if isinstance(value, bool) or value not in (0, 1):
                raise ValueError(f"{flag} must be 0 or 1, got: {value!r}")

    # --- Build WHERE clause dynamically (may end up empty) ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        plan_id = None
        try:
            plan_id = int(search_term)
        except ValueError:
            pass

        term_clauses = []
        if plan_id is not None:
            term_clauses.append("id = ?")
            params.append(plan_id)
        term_clauses.append("name LIKE ? COLLATE NOCASE")
        params.append(f"%{search_term}%")
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
            p.id,
            p.name,
            p.price,
            p.duration_weeks,
            p.max_trainings,
            p.is_unlimited,
            p.is_single,
            p.is_active,
            p.created_at,
            p.updated_at,
            (
                SELECT COUNT(*)
                FROM memberships m
                WHERE m.plan_id = p.id
            ) AS membership_count
        FROM plans p
        {where_sql}
        ORDER BY p.is_active DESC, p.name
    """

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No plans found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Plan search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except Exception as e:
        logger.exception(
            "Failed to search plans: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search plans: {e}") from e