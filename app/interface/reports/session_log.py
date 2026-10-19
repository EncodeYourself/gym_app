# app/interface/pages/reports/session_log.py

from datetime import date

import streamlit as st

from app.interface.reports._shared import run_report_query


SESSION_LOG_QUERY = """
    WITH session_subs AS (
        SELECT s.class_id, s.date, s.substitute_trainer_id
        FROM substitutions s
        WHERE s.id = (
            SELECT MAX(s2.id)
            FROM substitutions s2
            WHERE s2.class_id = s.class_id
              AND s2.date     = s.date
        )
    )
    SELECT
        a.class_id                            AS class_id,
        a.attendance_date                     AS attendance_date,
        c.name                                AS class_name,
        c.schedule_day                        AS schedule_day,
        c.start_time                          AS start_time,
        COALESCE(ss.substitute_trainer_id, c.instructor_id) AS instructor_id,
        COALESCE(
            t_sub.first_name  || ' ' || t_sub.last_name,
            t_orig.first_name || ' ' || t_orig.last_name
        )                                     AS instructor_name,
        (ss.substitute_trainer_id IS NOT NULL) AS was_substituted,
        COUNT(*)                              AS attendees,
        SUM(CASE WHEN a.attendance_type = 'membership' THEN 1 ELSE 0 END)
            AS attendees_membership,
        SUM(CASE WHEN a.attendance_type = 'trial' THEN 1 ELSE 0 END)
            AS attendees_trial,
        SUM(CASE WHEN a.attendance_type = 'debt' THEN 1 ELSE 0 END)
            AS attendees_debt
    FROM attendance a
    JOIN classes  c           ON c.id = a.class_id
    LEFT JOIN trainers t_orig ON t_orig.id = c.instructor_id
    LEFT JOIN session_subs ss ON ss.class_id = a.class_id
                              AND ss.date     = a.attendance_date
    LEFT JOIN trainers t_sub  ON t_sub.id = ss.substitute_trainer_id
    WHERE a.attendance_date >= ?
      AND a.attendance_date <= ?
    GROUP BY
        a.class_id,
        a.attendance_date
    ORDER BY
        a.attendance_date DESC,
        c.start_time
"""


def _fmt_date(iso: str) -> str:
    """'2026-10-19' -> 'Mon, Oct 19'."""
    d = date.fromisoformat(iso[:10])
    return d.strftime("%a, %b %d")


def _fmt_class(row: dict) -> str:
    return f"{row['start_time']} · {row['class_name']}"


def _fmt_instructor(row: dict) -> str:
    name = row["instructor_name"] or "(unassigned)"
    if row["was_substituted"]:
        name += " (sub)"
    return name


def render_session_log(date_from: date, date_to: date) -> None:
    """Render the flat session log: one row per class session."""
    params = (date_from.isoformat(), date_to.isoformat())
    rows = run_report_query(SESSION_LOG_QUERY, params, context="session_log")

    if not rows:
        st.info("No sessions recorded in this period.")
        return

    # --- Summary strip ---------------------------------------------------
    total_sessions = len(rows)
    total_attendees = sum(r["attendees"] for r in rows)
    avg_per_session = total_attendees / total_sessions

    c1, c2, c3 = st.columns(3)
    c1.metric("Sessions", total_sessions)
    c2.metric("Attendances", total_attendees)
    c3.metric("Avg / session", f"{avg_per_session:.1f}")

    st.caption(
        "Only sessions with at least one attendee are listed. "
        "Scheduled classes that nobody attended won't appear here — "
        "check the Class Health report for those."
    )

    st.divider()

    # --- Main session table ---------------------------------------------
    # Four columns, phone-friendly. Detailed breakdown available in the
    # expander below.
    display = [
        {
            "Date":        _fmt_date(r["attendance_date"]),
            "Class":       _fmt_class(r),
            "Instructor":  _fmt_instructor(r),
            "Attendees":   r["attendees"],
        }
        for r in rows
    ]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date":      st.column_config.TextColumn(width="medium"),
            "Class":     st.column_config.TextColumn(width="large"),
            "Instructor": st.column_config.TextColumn(width="medium"),
            "Attendees": st.column_config.NumberColumn(width="small"),
        },
    )

    st.divider()

    # --- Type breakdown --------------------------------------------------
    with st.expander("Attendance type breakdown"):
        st.caption(
            "Per-session split of members, trials, and debt attendances."
        )
        breakdown = [
            {
                "Date":         _fmt_date(r["attendance_date"]),
                "Class":        _fmt_class(r),
                "Membership":   r["attendees_membership"],
                "Trial":        r["attendees_trial"],
                "Debt":         r["attendees_debt"],
                "Total":        r["attendees"],
            }
            for r in rows
        ]
        st.dataframe(
            breakdown,
            use_container_width=True,
            hide_index=True,
        )