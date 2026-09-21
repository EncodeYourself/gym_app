from app.database.database_ctl import get_connection
import logging 
from typing import Any, Dict, Optional

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
            conn.commit()
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
        
def delete_plan(plan_id: int) -> bool:
    """
    Delete a plan from the catalog by id.

    Note: Consider using is_active=0 to deactivate plans instead of deleting,
    especially if payments or memberships reference this plan.

    Args:
        plan_id: Positive integer id of the plan to delete.

    Returns:
        True if the plan was deleted, False if it did not exist.

    Raises:
        ValueError: If plan_id is not a positive integer.
        RuntimeError: If the database operation fails.
    """

    # --- Validate plan_id ---
    if not isinstance(plan_id, int) or plan_id <= 0:
        raise ValueError(f"plan_id must be a positive integer, got: {plan_id}")

    # --- Execute delete ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM plans WHERE id = ?",
                (plan_id,)
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No plan found with id=%s", plan_id)
                return False

            logger.info("Plan deleted: id=%s", plan_id)
            return True

    except Exception as e:
        logger.exception("Failed to delete plan id=%s", plan_id)
        raise RuntimeError(f"Failed to delete plan: {e}") from e

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
            conn.commit()

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

