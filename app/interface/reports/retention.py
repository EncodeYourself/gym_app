# app/interface/pages/reports/retention.py

from datetime import date

import streamlit as st

from app.interface.reports._shared import run_report_query


# --- Snapshot: active members with their last-touch dates ---------------

MEMBER_SNAPSHOT_QUERY = """
    SELECT
        s.id              AS student_id,
        s.first_name      AS first_name,
        s.last_name       AS last_name,
        s.phone           AS phone,
        m.id              AS membership_id,
        m.start_date      AS start_date,
        m.expiry_date     AS expiry_date,
        m.used_trainings  AS used_trainings,
        pl.name           AS plan_name,
        pl.max_trainings  AS plan_max_trainings,
        pl.is_unlimited   AS plan_is_unlimited,
        (SELECT MAX(a.attendance_date)
           FROM attendance a
          WHERE a.student_id = s.id)                AS last_attendance_date,
        (SELECT MAX(date(p.payment_date))
           FROM payments p
          WHERE p.student_id = s.id
            AND p.status = 'paid')                  AS last_payment_date
    FROM students s
    JOIN memberships m
        ON m.id = (
            SELECT m2.id
              FROM memberships m2
             WHERE m2.student_id = s.id
               AND m2.status = 'active'
             ORDER BY m2.start_date DESC, m2.id DESC
             LIMIT 1
        )
    JOIN plans pl ON pl.id = m.plan_id
    WHERE s.status = 'active'
    ORDER BY last_attendance_date ASC
"""


# --- Period: new and ended memberships ---------------------------------

NEW_MEMBERS_QUERY = """
    SELECT COUNT(*) AS new_members
    FROM memberships
    WHERE date(start_date) >= ?
      AND date(start_date) <= ?
"""

ENDED_MEMBERSHIPS_QUERY = """
    SELECT
        status,
        COUNT(*) AS count,
        AVG(julianday(expiry_date) - julianday(start_date))
            AS avg_lifetime_days
    FROM memberships
    WHERE date(expiry_date) >= ?
      AND date(expiry_date) <= ?
      AND status IN ('expired', 'cancelled', 'completed', 'upgraded')
    GROUP BY status
"""


# --- Thresholds (hardcoded for now; per-report controls deferred) -------

SLIP_THRESHOLD_DAYS    = 14   # days since last visit → slipping
EXPIRING_SOON_DAYS     = 14   # days until expiry → renewal call
NEW_MEMBER_GRACE_DAYS  = 14   # grace period before flagging as slipping
TOP_N                  = 10   # max rows per at-risk list before "show all"


# --- Small helpers ------------------------------------------------------

def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    return (date.today() - date.fromisoformat(iso[:10])).days


def _days_until(iso: str | None) -> int | None:
    if not iso:
        return None
    return (date.fromisoformat(iso[:10]) - date.today()).days


def _display_name(row: dict) -> str:
    return f"{row.get('last_name', '')} {row.get('first_name', '')}".strip()


def _render_at_risk_list(rows: list[dict], extra_column: str, key: str) -> None:
    """Render a capped list with an expander showing the rest."""
    head = rows[:TOP_N]
    tail = rows[TOP_N:]

    def _row_view(r: dict) -> dict:
        return {
            "Student": _display_name(r),
            "Phone":   r.get("phone") or "—",
            extra_column: r.get("_extra") or "—",
            "Plan":    r.get("plan_name") or "—",
        }

    st.dataframe(
        [_row_view(r) for r in head],
        use_container_width=True,
        hide_index=True,
    )
    if tail:
        with st.expander(f"Show {len(tail)} more"):
            st.dataframe(
                [_row_view(r) for r in tail],
                use_container_width=True,
                hide_index=True,
            )


# --- Renderer -----------------------------------------------------------

def render_retention(date_from: date, date_to: date) -> None:
    """Render the retention report: churn summary + at-risk lists."""
    members = run_report_query(
        MEMBER_SNAPSHOT_QUERY, (),
        context="retention_snapshot",
    )

    new_rows = run_report_query(
        NEW_MEMBERS_QUERY,
        (date_from.isoformat(), date_to.isoformat()),
        context="retention_new_members",
    )
    ended_rows = run_report_query(
        ENDED_MEMBERSHIPS_QUERY,
        (date_from.isoformat(), date_to.isoformat()),
        context="retention_ended",
    )

    new_count = new_rows[0]["new_members"] if new_rows else 0

    real_churn = 0
    upgraded   = 0
    for r in ended_rows:
        if r["status"] == "upgraded":
            upgraded += r["count"]
        else:
            real_churn += r["count"]

    net = new_count - real_churn
    active_count = len(members)

    # --- Top metrics ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active members", active_count)
    c2.metric("New this period", new_count)
    c3.metric("Churned this period", real_churn)
    c4.metric(
        "Net change",
        f"{net:+d}",
        help="New minus churned. Upgrades are excluded from churn.",
    )

    st.divider()

    # --- At-risk lists ---
    st.subheader("At risk")
    st.caption(
        f"Snapshot as of today. Slipping = no visit in {SLIP_THRESHOLD_DAYS}+ "
        f"days. Expiring = within {EXPIRING_SOON_DAYS} days. "
        f"New members (< {NEW_MEMBER_GRACE_DAYS} days old) are excluded from "
        f"the slipping and paying lists."
    )

    # Slipping: last visit older than threshold, not brand new
    slipping = []
    for r in members:
        days_since_att = _days_since(r.get("last_attendance_date"))
        days_since_start = _days_since(r.get("start_date"))
        if days_since_start is None or days_since_start < NEW_MEMBER_GRACE_DAYS:
            continue
        if days_since_att is None or days_since_att >= SLIP_THRESHOLD_DAYS:
            r["_extra"] = (
                f"{days_since_att} days" if days_since_att is not None
                else "never attended"
            )
            slipping.append(r)

    if slipping:
        st.markdown(f"**⚠️ Slipping** — {len(slipping)} members")
        _render_at_risk_list(slipping, extra_column="Last seen", key="slip")
    else:
        st.success("No slipping members. Everyone's been seen recently.")

    st.divider()

    # Paying but not training: recent payment, no recent attendance
    paying_not_training = []
    for r in members:
        days_since_att = _days_since(r.get("last_attendance_date"))
        days_since_pay = _days_since(r.get("last_payment_date"))
        days_since_start = _days_since(r.get("start_date"))
        if days_since_start is None or days_since_start < NEW_MEMBER_GRACE_DAYS:
            continue
        if days_since_pay is None or days_since_pay > 60:
            continue
        if days_since_att is None or days_since_att >= SLIP_THRESHOLD_DAYS:
            r["_extra"] = f"paid {days_since_pay}d ago"
            paying_not_training.append(r)

    if paying_not_training:
        st.markdown(
            f"**💰 Paying but not training** — {len(paying_not_training)} members"
        )
        _render_at_risk_list(
            paying_not_training, extra_column="Last payment", key="paying"
        )
    else:
        st.success("Everyone who's paid recently has also been training.")

    st.divider()

    # Expiring soon
    expiring = []
    for r in members:
        days_to_exp = _days_until(r.get("expiry_date"))
        if days_to_exp is None:
            continue
        if 0 <= days_to_exp <= EXPIRING_SOON_DAYS:
            r["_extra"] = f"in {days_to_exp} days"
            expiring.append(r)

    if expiring:
        st.markdown(f"**🔔 Expiring soon** — {len(expiring)} members")
        _render_at_risk_list(expiring, extra_column="Expires", key="expiring")
    else:
        st.success(f"No memberships expiring in the next {EXPIRING_SOON_DAYS} days.")

    st.divider()

    # --- Churn detail ---
    st.subheader("Churn this period")

    if not ended_rows:
        st.caption("No memberships ended in this period.")
    else:
        status_labels = {
            "expired":   "Expired",
            "cancelled": "Cancelled",
            "completed": "Completed",
            "upgraded":  "Upgraded (not churn)",
        }

        churn_rows = []
        for r in ended_rows:
            avg_days = r.get("avg_lifetime_days")
            churn_rows.append({
                "Status":         status_labels.get(r["status"], r["status"]),
                "Count":          r["count"],
                "Avg lifetime":   f"{avg_days:.0f} days" if avg_days else "—",
            })

        if upgraded:
            st.caption(
                f"**{upgraded}** membership"
                f"{'s' if upgraded != 1 else ''} ended because of an upgrade. "
                f"Those students are still with us — not counted as churn."
            )

        st.dataframe(
            churn_rows,
            use_container_width=True,
            hide_index=True,
        )