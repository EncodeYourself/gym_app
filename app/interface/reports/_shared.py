import streamlit as st
from app.database.database_ctl import get_connection
import sqlite3
from app.interface.utils.logging import get_logger

logger = get_logger(__name__)

REPORT_REGISTRY = {
    "cash_flow":    "Cash Flow",
    "revenue":      "Revenue",
    "retention":    "Retention",
    "class_health": "Class Health",
    "expenses":     "Expenses",
    "receivables":  "Receivables",
    "session_log":  "Session Log",
}


# _shared.py
@st.cache_data(ttl=300)
def run_report_query(query: str, params: tuple, context: str = "") -> list[dict]:
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        label = f" ({context})" if context else ""
        logger.exception("Report query failed%s", label)
        raise RuntimeError(f"Report query failed: {e}") from e
