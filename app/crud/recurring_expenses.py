from app.database.database_ctl import get_connection
from datetime import datetime
import logging 
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ALLOWED_EXPENSES_FIELDS  = {
    'id', 'expense_date', 'category', 'amount', 
    'is_recurring', 'recurring_expense_id', 'notes'
}

VALID_CATEGORIES = {
    'rent', 'utilities', 'cleaning', 'salary', 'equipment',
    'repairs', 'marketing', 'taxes', 'other',
}

def add_expense(
    expense_date: str, 
    category: str, 
    amount: int, 
    is_recurring: int=0, 
    recurring_expense_id: Optional[int]=None,
    notes: Optional[str] = None):
    """
    Insert a new expense record.

    Args:
        expense_date: Date of expense in YYYY-MM-DD format.
        category: One of the valid expense categories.
        amount: Positive integer amount.
        is_recurring: 1 if generated from a recurring rule, otherwise 0.
        recurring_expense_id: Required if is_recurring=1.
        notes: Optional notes.

    Returns:
        The new expense id.

    Raises:
        ValueError: If validation fails.
        RuntimeError: If the database operation fails.
    """

    try:
        datetime.strptime(expense_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid expense_date: {expense_date}. Expected YYYY-MM-DD.")

    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {category}. Allowed: {sorted(VALID_CATEGORIES)}")

    if not isinstance(amount, int) or amount <= 0:
        raise ValueError(f"amount must be a positive integer, got: {amount}")

    if is_recurring not in (0, 1):
        raise ValueError(f"is_recurring must be 0 or 1, got: {is_recurring}")

    if is_recurring == 1 and recurring_expense_id is None:
        raise ValueError("recurring_expense_id is required when is_recurring=1")

    data = {
        'expense_date': expense_date,
        'category': category,
        'amount': amount,
        'is_recurring': is_recurring,
        'recurring_expense_id': recurring_expense_id,
        'notes': notes,
    }

    if notes is None:
        data.pop('notes')

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO expenses ({columns_str}) VALUES ({placeholders})"

    
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            conn.commit()
            new_id = cursor.lastrowid

        logger.info(
            "Expense added: id=%s, date=%s, category=%s, amount=%s",
            new_id,
            expense_date,
            category,
            amount,
        )
        return new_id

    except Exception as e:
        logger.exception('Failed to add expense for expense_date=%s, category=%s, amount=%s', 
                            expense_date, category, amount)
        raise RuntimeError(f'Failed to add expense: {e}') from e

def delete_expense(expense_id: int) -> bool:
    '''
    Delete an expense by id.

    Args:
        expense_id: int, x > 0

    Returns:
        True if the expense was deleted, False if it did not exist.

    Raises:
        ValueError: If expense_id is not a positive integer.
        RuntimeError: If the database operation fails.
    '''

    if not isinstance(expense_id, int) or expense_id <= 0:
        raise ValueError(f"expense_id must be a positive integer, got: {expense_id}")

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM expenses WHERE id = ?",
                (expense_id,)
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No expense found with id=%s", expense_id)
                return False

            logger.info("Expense deleted: id=%s", expense_id)
            return True

    except Exception as e:
        logger.exception("Failed to delete expense id=%s", expense_id)
        raise RuntimeError(f"Failed to delete expense: {e}") from e


def update_expense(expense_id: int, **kwargs: Any) -> bool:
    """
    Update an expense record by id.

    Only allowed fields can be updated. Unknown fields are ignored.

    Args:
        expense_id: Positive integer id of the expense to update.
        **kwargs: One or more fields to update. Allowed fields:
            expense_date, category, amount, is_recurring,
            recurring_expense_id, notes

    Returns:
        True if the update was successful, False if no valid fields were
        provided or no expense was found.

    Raises:
        ValueError: If expense_id is invalid or field validation fails.
        RuntimeError: If the database operation fails.
    """

    # --- Validate expense_id ---
    if not isinstance(expense_id, int) or expense_id <= 0:
        raise ValueError(f"expense_id must be a positive integer, got: {expense_id}")

    # --- Filter allowed fields ---
    updates: Dict[str, Any] = {
        key: value
        for key, value in kwargs.items()
        if key in ALLOWED_EXPENSES_FIELDS
    }

    if not updates:
        logger.warning("No valid fields provided for expense update id=%s", expense_id)
        return False

    # --- Validate individual fields ---
    if 'expense_date' in updates:
        try:
            datetime.strptime(updates['expense_date'], "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid expense_date: {updates['expense_date']}. Expected YYYY-MM-DD."
            )

    if 'category' in updates:
        if updates['category'] not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: {updates['category']}. "
                f"Allowed: {sorted(VALID_CATEGORIES)}"
            )

    if 'amount' in updates:
        amount = updates['amount']
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError(f"amount must be a positive integer, got: {amount}")

    if 'is_recurring' in updates:
        if updates['is_recurring'] not in (0, 1):
            raise ValueError(
                f"is_recurring must be 0 or 1, got: {updates['is_recurring']}"
            )

    if 'recurring_expense_id' in updates:
        rid = updates['recurring_expense_id']
        if rid is not None and (not isinstance(rid, int) or rid <= 0):
            raise ValueError(
                f"recurring_expense_id must be a positive integer or None, got: {rid}"
            )


    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [expense_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE expenses SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning("No expense found with id=%s", expense_id)
                return False

            logger.info(
                "Expense updated: id=%s, fields=%s",
                expense_id,
                list(updates.keys()),
            )
            return True

    except Exception as e:
        logger.exception("Failed to update expense id=%s", expense_id)
        raise RuntimeError(f"Failed to update expense: {e}") from e


