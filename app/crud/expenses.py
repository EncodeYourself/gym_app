from app.database.database_ctl import get_connection
from datetime import datetime
import logging 
from typing import Any, Dict, Optional, List
import sqlite3

logger = logging.getLogger(__name__)


ALLOWED_EXPENSE_FIELDS = {
    'payee_id',
    'expense_date',
    'category',
    'amount',
    'recurring_expense_id',
    'notes',
}

VALID_EXPENSE_CATEGORIES = {
    'rent', 'utilities', 'cleaning', 'salary',
    'equipment', 'repairs', 'marketing', 'taxes', 'other',
}


ALLOWED_EXPENSE_FILTERS = {
    'category',
    'payee_id',
    'recurring_expense_id',
    'date_from',
    'date_to',
}

def add_expense(
    payee_id: int,
    expense_date: str,
    category: str,
    amount: int,
    recurring_expense_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Insert a new expense record.

    Args:
        payee_id: Required. Positive integer id of the payee who
            received the money.
        expense_date: Required. Date of expense in YYYY-MM-DD format.
        category: Required. One of VALID_EXPENSE_CATEGORIES.
        amount: Required. Non-negative integer amount.
        recurring_expense_id: Optional. Set when this expense was
            generated from a recurring definition; leave None for
            manual entries.
        notes: Optional free text.

    Returns:
        The new expense id.

    Raises:
        ValueError: If validation fails, or payee_id /
            recurring_expense_id references a record that does not exist.
        RuntimeError: If the database operation fails.
    """

    # --- Validate payee_id ---
    if isinstance(payee_id, bool) or not isinstance(payee_id, int) or payee_id <= 0:
        raise ValueError(
            f"payee_id must be a positive integer, got: {payee_id!r}"
        )

    # --- Validate expense_date ---
    if not isinstance(expense_date, str) or not expense_date.strip():
        raise ValueError(
            f"expense_date must be a non-empty string, got: {expense_date!r}"
        )
    try:
        datetime.strptime(expense_date.strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid expense_date: {expense_date!r}. Expected YYYY-MM-DD."
        )
    expense_date = expense_date.strip()

    # --- Validate category ---
    if category not in VALID_EXPENSE_CATEGORIES:
        raise ValueError(
            f"Invalid category: {category}. "
            f"Expected one of: {sorted(VALID_EXPENSE_CATEGORIES)}"
        )

    # --- Validate amount ---
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError(
            f"amount must be a non-negative integer, got: {amount!r}"
        )

    # --- Validate recurring_expense_id ---
    if recurring_expense_id is not None:
        if isinstance(recurring_expense_id, bool) or not isinstance(recurring_expense_id, int) or recurring_expense_id <= 0:
            raise ValueError(
                f"recurring_expense_id must be a positive integer or None, "
                f"got: {recurring_expense_id!r}"
            )

    # --- Validate notes ---
    if notes is not None:
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string or None, got: {notes!r}")
        notes = notes.strip() or None

    # --- Build data (omit optional None fields so schema defaults apply) ---
    data: Dict[str, Any] = {
        'payee_id': payee_id,
        'expense_date': expense_date,
        'category': category,
        'amount': amount,
    }
    if recurring_expense_id is not None:
        data['recurring_expense_id'] = recurring_expense_id
    if notes is not None:
        data['notes'] = notes

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO expenses ({columns_str}) VALUES ({placeholders})"

    # --- Execute insert ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            new_id = cursor.lastrowid

        logger.info(
            "Expense added: id=%s, payee_id=%s, date=%s, category=%s, amount=%s",
            new_id, payee_id, expense_date, category, amount,
        )
        return new_id

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'foreign key' in msg:
            raise ValueError(
                "payee_id or recurring_expense_id references a record "
                "that does not exist."
            ) from e
        raise ValueError(f"Expense violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception(
            "Failed to add expense: payee_id=%s, date=%s, category=%s",
            payee_id, expense_date, category,
        )
        raise RuntimeError(f"Failed to add expense: {e}") from e

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

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        expense_id: Positive integer id of the expense to update.
        **kwargs: One or more fields to update. Allowed fields:
            payee_id, expense_date, category, amount,
            recurring_expense_id, notes

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no expense was found.

    Raises:
        ValueError: If expense_id is invalid, field validation fails,
            or a foreign key references a record that does not exist.
        RuntimeError: If the database operation fails.
    """

    # --- Validate expense_id ---
    if isinstance(expense_id, bool) or not isinstance(expense_id, int) or expense_id <= 0:
        raise ValueError(f"expense_id must be a positive integer, got: {expense_id!r}")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_EXPENSE_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for expense update id=%s", expense_id)
        return False

    # --- Validate individual fields ---
    if 'payee_id' in updates:
        value = updates['payee_id']
        # payee_id is NOT NULL in the schema — None is rejected, not stored.
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"payee_id must be a positive integer, got: {value!r}"
            )

    if 'expense_date' in updates:
        value = updates['expense_date']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"expense_date must be a non-empty string, got: {value!r}"
            )
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid expense_date: {value!r}. Expected YYYY-MM-DD."
            )
        updates['expense_date'] = value.strip()

    if 'category' in updates:
        value = updates['category']
        if value not in VALID_EXPENSE_CATEGORIES:
            raise ValueError(
                f"Invalid category: {value}. "
                f"Expected one of: {sorted(VALID_EXPENSE_CATEGORIES)}"
            )

    if 'amount' in updates:
        value = updates['amount']
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                f"amount must be a non-negative integer, got: {value!r}"
            )

    if 'recurring_expense_id' in updates and updates['recurring_expense_id'] is not None:
        value = updates['recurring_expense_id']
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"recurring_expense_id must be a positive integer or None, "
                f"got: {value!r}"
            )

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")
        updates['notes'] = value.strip() or None

    # --- Execute update ---
    # updated_at is handled by the trigger on this table — no manual set.
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [expense_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE expenses SET {set_clause} WHERE id = ?",
                values,
            )

            if cursor.rowcount == 0:
                logger.warning("No expense found with id=%s", expense_id)
                return False

        # Log after context exit — commit has fired, change is durable.
        logger.info(
            "Expense updated: id=%s, fields=%s",
            expense_id,
            list(updates.keys()),
        )
        return True

    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'foreign key' in msg:
            raise ValueError(
                "payee_id or recurring_expense_id references a record "
                "that does not exist."
            ) from e
        raise ValueError(f"Expense violates a constraint: {e}") from e

    except sqlite3.Error as e:
        logger.exception("Failed to update expense id=%s", expense_id)
        raise RuntimeError(f"Failed to update expense: {e}") from e


def find_expenses(
    search_term: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Search for expenses, or list them all if no arguments are given.

    Joins payees so callers get the payee's name alongside the raw
    payee_id. The payee join is INNER because payee_id is NOT NULL —
    every expense has a payee.

    Supports:
        - Exact match on expense id
        - Exact match on amount (when search_term is numeric)
        - Partial match on category (case-insensitive)
        - Partial match on notes (case-insensitive)
        - Partial match on payee name (case-insensitive)

    Filters (all optional, AND-ed with the search term):
        - category             (exact, one of VALID_EXPENSE_CATEGORIES)
        - payee_id             (exact; positive integer)
        - recurring_expense_id (exact; positive integer)
        - date_from            (YYYY-MM-DD, inclusive)
        - date_to              (YYYY-MM-DD, inclusive)

    Args:
        search_term: String to search for. If None or empty, the term
            is ignored and only filters apply.
        **kwargs: Optional filters. Passing None for a filter skips it.

    Returns:
        List of matching expense records as dictionaries, each
        including payee_name.

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
    unknown = set(kwargs) - ALLOWED_EXPENSE_FILTERS
    if unknown:
        raise ValueError(f"Unknown filters: {unknown}")

    # --- Validate filter values ---
    if kwargs.get('category') is not None:
        value = kwargs['category']
        if value not in VALID_EXPENSE_CATEGORIES:
            raise ValueError(
                f"Invalid category: {value}. "
                f"Expected one of: {sorted(VALID_EXPENSE_CATEGORIES)}"
            )

    for int_field in ('payee_id', 'recurring_expense_id'):
        if kwargs.get(int_field) is not None:
            value = kwargs[int_field]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"{int_field} must be a positive integer, got: {value!r}"
                )

    for date_field in ('date_from', 'date_to'):
        if kwargs.get(date_field) is not None:
            value = kwargs[date_field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{date_field} must be a non-empty string, got: {value!r}"
                )
            try:
                datetime.strptime(value.strip(), "%Y-%m-%d")
            except ValueError:
                raise ValueError(
                    f"Invalid {date_field}: {value!r}. Expected YYYY-MM-DD."
                )
            kwargs[date_field] = value.strip()

    if (
        kwargs.get('date_from') is not None
        and kwargs.get('date_to') is not None
        and kwargs['date_from'] > kwargs['date_to']
    ):
        raise ValueError(
            f"date_from ({kwargs['date_from']}) cannot be after "
            f"date_to ({kwargs['date_to']})."
        )

    # --- Build WHERE clause dynamically (may end up empty) ---
    where_parts: List[str] = []
    params: List[Any] = []

    # Term clauses: only if a term was actually given.
    if search_term is not None:
        term_clauses = []

        # Numeric term: match id OR amount.
        numeric = None
        try:
            numeric = int(search_term)
        except ValueError:
            pass

        if numeric is not None:
            term_clauses.append("e.id = ?")
            params.append(numeric)
            term_clauses.append("e.amount = ?")
            params.append(numeric)

        like = f"%{search_term}%"
        term_clauses.append("e.category LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("e.notes LIKE ? COLLATE NOCASE")
        params.append(like)
        term_clauses.append("p.name LIKE ? COLLATE NOCASE")
        params.append(like)

        where_parts.append("(" + " OR ".join(term_clauses) + ")")

    # Filter clauses: skip any that are None.
    filter_columns = {
        'category':             'e.category',
        'payee_id':             'e.payee_id',
        'recurring_expense_id': 'e.recurring_expense_id',
    }
    for field, value in kwargs.items():
        if value is None:
            continue
        if field == 'date_from':
            where_parts.append("e.expense_date >= ?")
            params.append(value)
        elif field == 'date_to':
            where_parts.append("e.expense_date <= ?")
            params.append(value)
        else:
            where_parts.append(f"{filter_columns[field]} = ?")
            params.append(value)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
        SELECT
            e.id,
            e.payee_id,
            e.expense_date,
            e.category,
            e.amount,
            e.recurring_expense_id,
            e.notes,
            e.created_at,
            e.updated_at,
            p.name AS payee_name
        FROM expenses e
        JOIN payees p ON p.id = e.payee_id
        {where_sql}
        ORDER BY e.expense_date DESC, e.id DESC
    """

    try:
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info(
                    "No expenses found: term=%s, filters=%s",
                    search_term,
                    kwargs,
                )
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Expense search: term=%s, filters=%s, results=%d",
                search_term,
                kwargs,
                len(results),
            )
            return results

    except sqlite3.Error as e:
        logger.exception(
            "Failed to search expenses: term=%s, filters=%s",
            search_term,
            kwargs,
        )
        raise RuntimeError(f"Failed to search expenses: {e}") from e

