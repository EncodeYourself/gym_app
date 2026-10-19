# app/interface/pages/reports/expenses.py

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from app.interface.reports._shared import run_report_query
from app.interface.utils.logging import get_logger

logger  = get_logger(__name__)

EXPENSES_QUERY = """
    SELECT
        strftime('%Y-%m', e.expense_date) AS month,
        e.category                        AS category,
        e.payee_id                        AS payee_id,
        pa.name                           AS payee_name,
        (e.recurring_expense_id IS NOT NULL) AS is_recurring,
        SUM(e.amount)                     AS amount,
        COUNT(*)                          AS expense_count
    FROM expenses e
    JOIN payees pa ON pa.id = e.payee_id
    WHERE e.expense_date >= ?
      AND e.expense_date <= ?
    GROUP BY
        strftime('%Y-%m', e.expense_date),
        e.category,
        e.payee_id,
        (e.recurring_expense_id IS NOT NULL)
    ORDER BY
        month,
        category,
        amount DESC
"""


# Category display order — largest-cost categories first.
CATEGORY_ORDER = [
    "rent",
    "salary",
    "utilities",
    "equipment",
    "repairs",
    "marketing",
    "cleaning",
    "taxes",
    "other",
]

# Colors per category, used consistently across chart and trend.
CATEGORY_COLORS = {
    "rent":      "#1565C0",
    "salary":    "#4CAF50",
    "utilities": "#FF9800",
    "equipment": "#7E57C2",
    "repairs":   "#795548",
    "marketing": "#E91E63",
    "cleaning":  "#00BCD4",
    "taxes":     "#607D8B",
    "other":     "#9E9E9E",
}


def render_expenses(date_from: date, date_to: date) -> None:
    """Render the expenses report: summary, split, breakdown, trend."""
    params = (date_from.isoformat(), date_to.isoformat())
    rows = run_report_query(EXPENSES_QUERY, params, context="expenses")

    if not rows:
        st.info("No expenses in this period.")
        return

    # --- Aggregate in Python (all views come from the same rows) ---
    total_spent   = sum(r["amount"] for r in rows)
    total_entries = sum(r["expense_count"] for r in rows)

    by_category: dict[str, dict] = {}
    by_payee:    dict[str, dict] = {}
    by_recurring = {0: {"amount": 0, "count": 0}, 1: {"amount": 0, "count": 0}}
    by_month_category: dict[tuple[str, str], int] = {}

    for r in rows:
        cat = r["category"]
        b = by_category.setdefault(cat, {"amount": 0, "count": 0})
        b["amount"] += r["amount"]
        b["count"]  += r["expense_count"]

        payee = r["payee_name"]
        p = by_payee.setdefault(payee, {"amount": 0, "count": 0})
        p["amount"] += r["amount"]
        p["count"]  += r["expense_count"]

        rec = int(r["is_recurring"])
        by_recurring[rec]["amount"] += r["amount"]
        by_recurring[rec]["count"]  += r["expense_count"]

        key = (r["month"], cat)
        by_month_category[key] = by_month_category.get(key, 0) + r["amount"]

    months = sorted({r["month"] for r in rows})

    # --- Top metrics ---
    col_a, col_b = st.columns(2)
    col_a.metric("Total spent", f"{total_spent:,} ₽")
    col_b.metric("Entries", total_entries)

    st.divider()

    # --- Recurring vs one-off split ---
    st.subheader("Recurring vs one-off")

    recurring_amt = by_recurring[1]["amount"]
    oneoff_amt    = by_recurring[0]["amount"]

    col_r, col_o = st.columns(2)
    col_r.metric(
        "Recurring baseline",
        f"{recurring_amt:,} ₽",
        delta=(
            f"{recurring_amt / total_spent * 100:.0f}% of total"
            if total_spent else None
        ),
        delta_color="off",
    )
    col_o.metric(
        "One-off spend",
        f"{oneoff_amt:,} ₽",
        delta=(
            f"{oneoff_amt / total_spent * 100:.0f}% of total"
            if total_spent else None
        ),
        delta_color="off",
    )
    st.caption(
        "The recurring baseline is what the gym costs to run in a normal "
        "month. One-off spend is above that — purchases, repairs, and "
        "anything that doesn't recur."
    )

    st.divider()

    # --- Category breakdown ---
    st.subheader("By category")

    ordered_cats = [c for c in CATEGORY_ORDER if c in by_category] + [
        c for c in by_category if c not in CATEGORY_ORDER
    ]

    if ordered_cats:
        fig = go.Figure(
            go.Bar(
                x=[by_category[c]["amount"] for c in ordered_cats],
                y=ordered_cats,
                orientation="h",
                marker_color=[CATEGORY_COLORS.get(c, "#9E9E9E") for c in ordered_cats],
                text=[f"{by_category[c]['amount']:,} ₽" for c in ordered_cats],
                textposition="outside",
                hovertemplate="%{y}: %{x:,.0f} ₽<extra></extra>",
            )
        )
        fig.update_layout(
            height=340,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title=None, showticklabels=False, showgrid=False),
            yaxis=dict(title=None, autorange="reversed"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Payee table ---
    st.subheader("By payee")

    payee_rows = []
    for name, data in sorted(
        by_payee.items(), key=lambda kv: kv[1]["amount"], reverse=True
    ):
        payee_rows.append({
            "Payee":      name,
            "Amount":     data["amount"],
            "Entries":    data["count"],
            "Share":      f"{data['amount'] / total_spent * 100:.1f}%"
                          if total_spent else "—",
        })

    st.dataframe(
        payee_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Amount": st.column_config.NumberColumn(format="%d ₽"),
        },
    )

    st.divider()

    # --- Trend: stacked bars per month, split by category ---
    st.subheader("Trend")

    if len(months) < 2:
        st.caption("Trend appears once the period spans more than one month.")
    else:
        fig = go.Figure()
        for cat in ordered_cats:
            fig.add_trace(go.Bar(
                x=months,
                y=[by_month_category.get((m, cat), 0) for m in months],
                name=cat,
                marker_color=CATEGORY_COLORS.get(cat, "#9E9E9E"),
                hovertemplate="%{x} · " + cat + ": %{y:,.0f} ₽<extra></extra>",
            ))
        fig.update_layout(
            barmode="stack",
            height=380,
            margin=dict(l=0, r=0, t=10, b=0),
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