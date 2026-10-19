# app/interface/pages/10_reports.py

import datetime
import streamlit as st
from app.interface.reports import session_log
from app.interface.utils.logging import get_logger
import app.interface.reports.cash_flow as cash_flow
import app.interface.reports.revenue as revenue
import app.interface.reports.expenses as expenses
import app.interface.reports.retention as retention
import app.interface.reports.class_health as class_health
from app.database.database_ctl import get_connection
from app.interface.reports._shared import REPORT_REGISTRY, run_report_query

# --- Report registry ---------------------------------------------------------
# Each report is identified by a short key and has a display label.
# As reports get built out, each entry grows a preview function (returns a
# headline string for the current period) and a render function (draws the
# full report). For now, both are placeholders.

PERIOD_PRESETS = [
    "This Month",
    "Last Month",
    "This Quarter",
    "This Year",
    "Custom",
]

logger = get_logger(__name__)

def _compute_period_range(preset: str) -> tuple[datetime.date, datetime.date]:
    """Return inclusive (start, end) dates for a named period preset."""
    today = datetime.date.today()

    if preset == "This Month":
        start = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        end = next_month - datetime.timedelta(days=1)

    elif preset == "Last Month":
        first_of_this = today.replace(day=1)
        end = first_of_this - datetime.timedelta(days=1)
        start = end.replace(day=1)

    elif preset == "This Quarter":
        q = (today.month - 1) // 3
        start = datetime.date(today.year, q * 3 + 1, 1)
        end_month = q * 3 + 3
        if end_month == 12:
            next_q = datetime.date(today.year + 1, 1, 1)
        else:
            next_q = datetime.date(today.year, end_month + 1, 1)
        end = next_q - datetime.timedelta(days=1)

    elif preset == "This Year":
        start = datetime.date(today.year, 1, 1)
        end = datetime.date(today.year, 12, 31)

    else:
        # "Custom" is handled by the caller before this is reached.
        start = today.replace(day=1)
        end = today

    return start, end

# --- Page header -------------------------------------------------------------
st.title("📈 Reports")


# --- Period selector ---------------------------------------------------------
st.subheader("Period")

period_preset = st.radio(
    "Period",
    options=PERIOD_PRESETS,
    index=0,
    horizontal=True,
    label_visibility="collapsed",
    key="reports_period_preset",
)

if period_preset == "Custom":
    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input(
            "From",
            value=datetime.date.today().replace(day=1),
            key="reports_date_from",
        )
    with col_to:
        date_to = st.date_input(
            "To",
            value=datetime.date.today(),
            key="reports_date_to",
        )
else:
    date_from, date_to = _compute_period_range(period_preset)

if date_from > date_to:
    st.error(f"From ({date_from}) cannot be after To ({date_to}).")
    st.stop()

st.caption(f"Showing **{date_from.isoformat()}** → **{date_to.isoformat()}**")

st.divider()


# --- Report picker -----------------------------------------------------------
report_keys = list(REPORT_REGISTRY.keys())

selected_report_key = st.radio(
    "Report",
    options=report_keys,
    format_func=lambda k: REPORT_REGISTRY[k],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
    key="reports_selected",
)

# --- Report dispatch ---------------------------------------------------------

RENDERERS = {
    "cash_flow": cash_flow.render_cash_flow,
    "revenue":     revenue.render_revenue,      # to be added
    "retention":   retention.render_retention,
    "class_health": class_health.render_class_health,
    "expenses":    expenses.render_expenses,
    # "receivables": render_receivables,
    "session_log": session_log.render_session_log
}

selected_report_label = REPORT_REGISTRY[selected_report_key]

st.divider()
st.subheader(selected_report_label)

renderer = RENDERERS.get(selected_report_key)
if renderer is None:
    st.info(
        f"The **{selected_report_label}** report is not yet implemented."
    )
else:
    RENDERERS[selected_report_key](
        date_from, 
        date_to)

