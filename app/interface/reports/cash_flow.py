from datetime import date
from app.database.database_ctl import get_connection
from app.interface.reports import _shared
import sqlite3
import streamlit as st
from app.interface.utils.logging import get_logger
import plotly.graph_objects as go

logger = get_logger(__name__)

CASH_FLOW_QUERY = """
        SELECT
            month,
            SUM(cash_in)  AS cash_in,
            SUM(cash_out) AS cash_out,
            SUM(cash_in) - SUM(cash_out) AS net
        FROM (
            SELECT strftime('%Y-%m', payment_date) AS month,
                   amount_paid AS cash_in,
                   0 AS cash_out
            FROM payments
            WHERE status = 'paid'
              AND date(payment_date) >= ?
              AND date(payment_date) <= ?
            UNION ALL
            SELECT strftime('%Y-%m', expense_date) AS month,
                   0 AS cash_in,
                   amount AS cash_out
            FROM expenses
            WHERE expense_date >= ?
              AND expense_date <= ?
        )
        GROUP BY month
        ORDER BY month
    """

def render_cash_flow(date_from: date, date_to: date) -> None:
    """Render the cash flow report: metrics + chart + table."""
    start = date_from.isoformat()
    end = date_to.isoformat()
    rows = _shared.run_report_query(
        CASH_FLOW_QUERY, 
        (start, end, start, end), 
        context="cash_flow"
    )

    if not rows:
        st.info("No cash movement in this period.")
        return

    months   = [r["month"]    for r in rows]
    cash_in  = [r["cash_in"]  for r in rows]
    cash_out = [r["cash_out"] for r in rows]
    net      = [r["net"]      for r in rows]

    # --- Summary line for the period ---
    total_in  = sum(cash_in)
    total_out = sum(cash_out)
    total_net = sum(net)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Cash in",  f"{total_in:,} ₽")
    col_b.metric("Cash out", f"{total_out:,} ₽")
    col_c.metric("Net",      f"{total_net:+,} ₽")

    # --- Chart ---
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=months, y=cash_in,
        name="Cash in",
        marker_color="#4CAF50",
        hovertemplate="In: %{y:,.0f} ₽<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=months, y=[-v for v in cash_out],
        name="Cash out",
        marker_color="#F44336",
        customdata=cash_out,
        hovertemplate="Out: %{customdata:,.0f} ₽<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=net,
        name="Net",
        mode="lines+markers",
        line=dict(color="#1565C0", width=3),
        marker=dict(size=8),
        hovertemplate="Net: %{y:+,.0f} ₽<extra></extra>",
    ))

    fig.update_layout(
        barmode="group",
        height=420,
        margin=dict(l=0, r=0, t=30, b=0),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
        ),
        yaxis=dict(tickformat=",.0f", title=None),
        xaxis=dict(title=None),
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Table below the chart ---
    st.dataframe(
        [
            {
                "Month":    r["month"],
                "Cash In":  r["cash_in"],
                "Cash Out": r["cash_out"],
                "Net":      r["net"],
            }
            for r in rows
        ],
        use_container_width=True,
        hide_index=True,
    )