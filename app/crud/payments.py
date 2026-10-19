from app.database.database_ctl import get_connection
from datetime import datetime
import logging
import sqlite3
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

ALLOWED_PAYMENT_METHODS = {
    'cash',
    'card',
    'bank_transfer',
    'other',
}

ALLOWED_PAYMENTS_FIELDS = {
    'student_id',
    'plan_id',
    'amount_paid',
    'payment_date',
    'method',
    'receipt_number',
    'notes'
}

VALID_PAYMENT_STATUSES = {
    'paid',
    'refunded',
    'voided',
}

def add_payment(
    student_id: int,
    plan_id: int,
    amount_paid: int,
    method: str,
    payment_date: Optional[str] = None,
    receipt_number: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = 'paid',
) -> int | None:
    """
    Insert a new payment record.

    Args:
        student_id: Positive integer id of the student who paid.
        plan_id: Positive integer id of the plan purchased.
        amount_paid: Amount paid in rubles. Must be a positive integer.
        method: Payment method. One of: cash, card, bank_transfer, other.
        payment_date: Date of payment in YYYY-MM-DD format.
            Defaults to current date if not provided.
        receipt_number: Optional unique receipt number.
        notes: Optional notes.
        status: Payment status. One of: paid, refunded, voided.
            Defaults to 'paid'.

    Returns:
        The new payment id.

    Raises:
        ValueError: If any field fails validation.
        RuntimeError: If the database operation fails.
    """

    # --- Validate student_id ---
    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(f"student_id must be a positive integer, got: {student_id}")

    # --- Validate plan_id ---
    if not isinstance(plan_id, int) or plan_id <= 0:
        raise ValueError(f"plan_id must be a positive integer, got: {plan_id}")

    # --- Validate amount_paid ---
    if not isinstance(amount_paid, int) or amount_paid <= 0:
        raise ValueError(f"amount_paid must be a positive integer, got: {amount_paid}")

    # --- Validate method ---
    if method not in ALLOWED_PAYMENT_METHODS:
        raise ValueError(
            f"Invalid method: {method}. "
            f"Expected one of: {sorted(ALLOWED_PAYMENT_METHODS)}"
        )

    # --- Validate status ---
    if status not in VALID_PAYMENT_STATUSES:
        raise ValueError(
            f"Invalid status: {status}. "
            f"Expected one of: {sorted(VALID_PAYMENT_STATUSES)}"
        )

    # --- Validate payment_date ---
    if payment_date is None:
        payment_date = datetime.now().strftime("%Y-%m-%d")
    else:
        if not isinstance(payment_date, str):
            raise ValueError(f"payment_date must be a string or None, got: {payment_date!r}")
        try:
            datetime.strptime(payment_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid payment_date: {payment_date}. Expected YYYY-MM-DD."
            )

    # --- Validate receipt_number ---
    if receipt_number is not None:
        if not isinstance(receipt_number, str) or not receipt_number.strip():
            raise ValueError(
                f"receipt_number must be a non-empty string or None, "
                f"got: {receipt_number!r}"
            )
        receipt_number = receipt_number.strip()

    # --- Validate notes ---
    if notes is not None:
        if not isinstance(notes, str):
            raise ValueError(f"notes must be a string or None, got: {notes!r}")

    # --- Build data ---
    data: Dict[str, Any] = {
        'student_id': student_id,
        'plan_id': plan_id,
        'amount_paid': amount_paid,
        'payment_date': payment_date,
        'method': method,
        'status': status,
    }

    if receipt_number is not None:
        data['receipt_number'] = receipt_number

    if notes is not None:
        data['notes'] = notes

    placeholders = ', '.join(['?'] * len(data))
    columns_str = ', '.join(data.keys())
    query = f"INSERT INTO payments ({columns_str}) VALUES ({placeholders})"

    # --- Execute insert ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            
            new_id = cursor.lastrowid

        logger.info(
            "Payment added: id=%s, student_id=%s, plan_id=%s, amount=%s, method=%s, status=%s",
            new_id,
            student_id,
            plan_id,
            amount_paid,
            method,
            status,
        )
        return new_id

    except Exception as e:
        logger.exception(
            "Failed to add payment: student_id=%s, amount=%s",
            student_id,
            amount_paid,
        )
        raise RuntimeError(f"Failed to add payment: {e}") from e

def delete_payment(payment_id: int) -> bool:
    """
    Delete a payment record by id.

    Warning: This permanently removes the payment from financial history.
    Consider whether a refund or reversal record is more appropriate
    before deleting.

    Args:
        payment_id: Positive integer id of the payment to delete.

    Returns:
        True if the payment was deleted, False if it did not exist.

    Raises:
        ValueError: If payment_id is not a positive integer.
        RuntimeError: If the database operation fails.
    """

    # --- Validate payment_id ---
    if not isinstance(payment_id, int) or payment_id <= 0:
        raise ValueError(f"payment_id must be a positive integer, got: {payment_id}")

    # --- Execute delete ---
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM payments WHERE id = ?",
                (payment_id,)
            )
            

            if cursor.rowcount == 0:
                logger.warning("No payment found with id=%s", payment_id)
                return False

            logger.info("Payment deleted: id=%s", payment_id)
            return True

    except Exception as e:
        logger.exception("Failed to delete payment id=%s", payment_id)
        raise RuntimeError(f"Failed to delete payment: {e}") from e

def update_payment(payment_id: int, **kwargs: Any) -> bool:
    """
    Update a payment record by id.

    Only allowed fields can be updated. Unknown fields raise an error.

    Args:
        payment_id: Positive integer id of the payment to update.
        **kwargs: One or more fields to update. Allowed fields:
            student_id, plan_id, amount_paid, payment_date,
            method, receipt_number, notes, status

    Returns:
        True if the update was successful, False if no valid fields
        were provided or no payment was found.

    Raises:
        ValueError: If payment_id is invalid or field validation fails.
        RuntimeError: If the database operation fails.
    """

    # --- Validate payment_id ---
    if not isinstance(payment_id, int) or payment_id <= 0:
        raise ValueError(f"payment_id must be a positive integer, got: {payment_id}")

    # --- Detect unknown fields ---
    unknown = set(kwargs) - ALLOWED_PAYMENTS_FIELDS
    if unknown:
        raise ValueError(f"Unknown fields: {unknown}")

    # --- Build updates ---
    updates: Dict[str, Any] = dict(kwargs)

    if not updates:
        logger.warning("No valid fields provided for payment update id=%s", payment_id)
        return False

    # --- Validate individual fields ---
    if 'student_id' in updates:
        value = updates['student_id']
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"student_id must be a positive integer, got: {value!r}")

    if 'plan_id' in updates:
        value = updates['plan_id']
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"plan_id must be a positive integer, got: {value}")

    if 'amount_paid' in updates:
        value = updates['amount_paid']
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"amount_paid must be a positive integer, got: {value}")
        
    if 'payment_date' in updates:
        value = updates['payment_date']
        if not isinstance(value, str):
            raise ValueError(f"payment_date must be a string, got: {value!r}")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid payment_date: {value}. Expected YYYY-MM-DD."
            )

    if 'method' in updates:
        value = updates['method']
        if value not in ALLOWED_PAYMENT_METHODS:
            raise ValueError(
                f"Invalid method: {value}. "
                f"Expected one of: {sorted(ALLOWED_PAYMENT_METHODS)}"
            )

    if 'receipt_number' in updates and updates['receipt_number'] is not None:
        value = updates['receipt_number']
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"receipt_number must be a non-empty string or None, got: {value!r}"
            )
        updates['receipt_number'] = value.strip()

    if 'notes' in updates and updates['notes'] is not None:
        value = updates['notes']
        if not isinstance(value, str):
            raise ValueError(f"notes must be a string or None, got: {value!r}")

    if 'status' in updates:
        value = updates['status']
        if value not in VALID_PAYMENT_STATUSES:
            raise ValueError(
                f"Invalid status: {value}. "
                f"Expected one of: {sorted(VALID_PAYMENT_STATUSES)}"
            )

    # --- Execute update ---
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [payment_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE payments SET {set_clause} WHERE id = ?",
                values
            )
            

            if cursor.rowcount == 0:
                logger.warning("No payment found with id=%s", payment_id)
                return False

            logger.info(
                "Payment updated: id=%s, fields=%s",
                payment_id,
                list(updates.keys()),
            )
            return True

    except Exception as e:
        logger.exception("Failed to update payment id=%s", payment_id)
        raise RuntimeError(f"Failed to update payment: {e}") from e

def search_payments(search_term: str) -> List[Dict[str, Any]]:
    """
    Search for payments by student id or payment date.

    Supports:
        - Exact match on student_id (when search_term is numeric)
        - Partial match on payment_date (case-insensitive, e.g. '2024-03')

    Args:
        search_term: String to search for. Can be a numeric student id
                     or a date fragment (YYYY, YYYY-MM, YYYY-MM-DD).

    Returns:
        List of matching payment records as dictionaries.

    Raises:
        ValueError: If search_term is empty or invalid.
        RuntimeError: If the database operation fails.
    """

    if not isinstance(search_term, str) or not search_term.strip():
        raise ValueError(f"search_term must be a non-empty string, got: {search_term!r}")

    search_term = search_term.strip()

    student_id = None
    try:
        student_id = int(search_term)
    except ValueError:
        pass

    query = """
        SELECT
            id,
            student_id,
            plan_id,
            amount_paid,
            payment_date,
            method,
            receipt_number,
            notes,
            status,
            created_at,
            updated_at
        FROM payments
        WHERE (? IS NOT NULL AND student_id = ?)
           OR payment_date LIKE ?
           OR receipt_number LIKE ? COLLATE NOCASE
        ORDER BY payment_date DESC, id DESC
        LIMIT 50
    """

    params = (
        student_id,
        student_id,
        f"%{search_term}%",
        f"%{search_term}%",
    )

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.info("No payments found for search term: %s", search_term)
                return []

            results = [dict(row) for row in rows]

            logger.info(
                "Payment search: term=%s, results=%d",
                search_term,
                len(results),
            )
            return results

    except Exception as e:
        logger.exception("Failed to search payments with term=%s", search_term)
        raise RuntimeError(f"Failed to search payments: {e}") from e