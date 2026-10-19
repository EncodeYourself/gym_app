from datetime import date
from app.database.database_ctl import get_connection
from app.interface.reports import _shared
import sqlite3
import streamlit as st
from app.interface.utils.logging import get_logger
import plotly.graph_objects as go

logger = get_logger(__name__)

REVENUE_QUERY = '''
    SELECT
        strftime('%Y-%m', p.payment_date) AS month,
        p.payment_category                AS category,
        p.plan_id                         AS plan_id,
        COALESCE(pl.name, '(no plan)')    AS plan_name,
        SUM(p.amount_paid)                AS revenue,
        COUNT(*)                          AS payment_count
    FROM payments p
    LEFT JOIN plans pl ON pl.id = p.plan_id
    WHERE p.status = 'paid'
    AND date(p.payment_date) >= ?
    AND date(p.payment_date) <= ?
    GROUP BY
        strftime('%Y-%m', p.payment_date),
        p.payment_category,
        p.plan_id
    ORDER BY
        month,
        category,
        revenue DESC
'''

# Category display order — most-important first.
CATEGORY_ORDER = [
    "membership_new",
    "membership_renewal",
    "membership_upgrade",
    "drop_in",
    "credit_payment",
    "refund",
    "other",
]

# Colors per category, used consistently across chart and any future view.
CATEGORY_COLORS = {
    "membership_new":     "#4CAF50",
    "membership_renewal": "#1565C0",
    "membership_upgrade": "#7E57C2",
    "drop_in":            "#FF9800",
    "credit_payment":     "#795548",
    "refund":             "#F44336",
    "other":              "#9E9E9E",
}


def render_revenue(date_from: date, date_to: date) -> None:
    """Render the revenue report: summary, breakdown, trend."""
    params = (date_from.isoformat(), date_to.isoformat())
    rows = _shared.run_report_query(REVENUE_QUERY, params, context="revenue")

    if not rows:
        st.info("No revenue in this period.")
        return

    # --- Aggregate in Python (all views come from the same rows) ---
    total_revenue = sum(r["revenue"] for r in rows)
    total_payments = sum(r["payment_count"] for r in rows)

    by_category: dict[str, dict] = {}
    for r in rows:
        cat = r["category"]
        bucket = by_category.setdefault(cat, {"revenue": 0, "count": 0})
        bucket["revenue"] += r["revenue"]
        bucket["count"]   += r["payment_count"]

    by_month_category: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r["month"], r["category"])
        by_month_category[key] = by_month_category.get(key, 0) + r["revenue"]

    months = sorted({r["month"] for r in rows})

    # --- Top metrics ---
    col_a, col_b = st.columns(2)
    col_a.metric("Total revenue", f"{total_revenue:,} ₽")
    col_b.metric("Payments", total_payments)

    st.divider()

    # --- Category breakdown ---
    st.subheader("By category")

    ordered_cats = [
        c for c in CATEGORY_ORDER if c in by_category
    ] + [
        c for c in by_category if c not in CATEGORY_ORDER
    ]

    if ordered_cats:
        fig = go.Figure(
            go.Bar(
                x=[by_category[c]["revenue"] for c in ordered_cats],
                y=ordered_cats,
                orientation="h",
                marker_color=[CATEGORY_COLORS.get(c, "#9E9E9E") for c in ordered_cats],
                text=[f"{by_category[c]['revenue']:,} ₽" for c in ordered_cats],
                textposition="outside",
                hovertemplate="%{y}: %{x:,.0f} ₽<extra></extra>",
            )
        )
        fig.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title=None, showticklabels=False, showgrid=False),
            yaxis=dict(title=None, autorange="reversed"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Category + plan table ---
    st.subheader("By plan")

    plan_rows = []
    for cat in ordered_cats:
        cat_rows = [r for r in rows if r["category"] == cat]
        cat_revenue = by_category[cat]["revenue"]

        # Group plans within this category across all months.
        by_plan: dict[str, dict] = {}
        for r in cat_rows:
            name = r["plan_name"]
            bucket = by_plan.setdefault(name, {"revenue": 0, "count": 0})
            bucket["revenue"] += r["revenue"]
            bucket["count"]   += r["payment_count"]

        for name, data in sorted(
            by_plan.items(), key=lambda kv: kv[1]["revenue"], reverse=True
        ):
            plan_rows.append({
                "Category":   cat,
                "Plan":       name,
                "Revenue":    data["revenue"],
                "Payments":   data["count"],
                "Share":      f"{data['revenue'] / total_revenue * 100:.1f}%"
                              if total_revenue else "—",
            })

        plan_rows.append({
            "Category":   f"  {cat} — subtotal",
            "Plan":       "",
            "Revenue":    cat_revenue,
            "Payments":   by_category[cat]["count"],
            "Share":      f"{cat_revenue / total_revenue * 100:.1f}%"
                          if total_revenue else "—",
        })

    st.dataframe(
        plan_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Revenue": st.column_config.NumberColumn(format="%d ₽"),
        },
    )

    st.divider()

    # --- Trend: stacked bars, one per month, split by category ---
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