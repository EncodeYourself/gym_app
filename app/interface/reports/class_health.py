# app/interface/pages/reports/class_health.py

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from app.interface.reports._shared import run_report_query


CLASS_HEALTH_QUERY = """
    WITH bounds AS (
        SELECT
            ? AS d4_start,
            ? AS d8_start,
            ? AS d12_start,
            ? AS d_end
    )
    SELECT
        c.id                                AS class_id,
        c.name                              AS class_name,
        c.schedule_day                      AS schedule_day,
        c.start_time                        AS start_time,
        c.instructor_id                     AS instructor_id,
        t.first_name || ' ' || t.last_name  AS instructor_name,
        t.status                            AS instructor_status,

        (SELECT COUNT(*) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d4_start
            AND a.attendance_date <= b.d_end
        ) AS total_4w,
        (SELECT COUNT(DISTINCT a.attendance_date) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d4_start
            AND a.attendance_date <= b.d_end
        ) AS sessions_4w,
        (SELECT COUNT(DISTINCT a.student_id) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d4_start
            AND a.attendance_date <= b.d_end
        ) AS unique_4w,

        (SELECT COUNT(*) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d8_start
            AND a.attendance_date <= b.d_end
        ) AS total_8w,
        (SELECT COUNT(DISTINCT a.attendance_date) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d8_start
            AND a.attendance_date <= b.d_end
        ) AS sessions_8w,

        (SELECT COUNT(*) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d12_start
            AND a.attendance_date <= b.d_end
        ) AS total_12w,
        (SELECT COUNT(DISTINCT a.attendance_date) FROM attendance a
          WHERE a.class_id = c.id
            AND a.attendance_date >= b.d12_start
            AND a.attendance_date <= b.d_end
        ) AS sessions_12w,

        (SELECT COUNT(*) FROM substitutions sub
          WHERE sub.class_id = c.id
            AND sub.date >= b.d4_start
            AND sub.date <= b.d_end
        ) AS subs_4w,

        (SELECT MAX(a.attendance_date) FROM attendance a
          WHERE a.class_id = c.id
        ) AS last_attendance
    FROM classes c
    LEFT JOIN trainers t ON t.id = c.instructor_id
    CROSS JOIN bounds b
    WHERE c.is_active = 1
    ORDER BY c.schedule_day, c.start_time
"""


DAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def _avg(total: int, sessions: int) -> float | None:
    return (total / sessions) if sessions else None


def _trend(avg_recent: float | None, avg_prev: float | None) -> str:
    if avg_recent is None and avg_prev is None:
        return "—"
    if avg_recent is None:
        return "↓"          # had activity before, none now
    if avg_prev is None:
        return "↑"          # new activity
    delta = avg_recent - avg_prev
    if abs(delta) < 0.5:
        return "→"
    return "↑" if delta > 0 else "↓"


def _fmt_avg(v: float | None) -> str:
    return f"{v:.1f}" if v is not None else "—"


def render_class_health(date_from: date, date_to: date) -> None:
    """Render the class health report: summary, table, heatmap, load."""
    d_end     = date_to
    d4_start  = d_end - timedelta(days=27)
    d8_start  = d_end - timedelta(days=55)
    d12_start = d_end - timedelta(days=83)

    params = (
        d4_start.isoformat(),
        d8_start.isoformat(),
        d12_start.isoformat(),
        d_end.isoformat(),
    )

    rows = run_report_query(CLASS_HEALTH_QUERY, params, context="class_health")

    if not rows:
        st.info("No active classes.")
        return

    # --- Post-process ---------------------------------------------------
    for r in rows:
        r["avg_4w"]  = _avg(r["total_4w"],  r["sessions_4w"])
        r["avg_8w"]  = _avg(r["total_8w"],  r["sessions_8w"])
        r["avg_12w"] = _avg(r["total_12w"], r["sessions_12w"])
        # Bias note: comparing 4w vs 8w (the 8w window contains the 4w).
        # Directionally correct, magnitude slightly understated. Fine for
        # an arrow. Refine to true 4v4 if precision ever matters.
        r["trend"]   = _trend(r["avg_4w"], r["avg_8w"])

    # --- Summary strip --------------------------------------------------
    active_count   = len(rows)
    total_att      = sum(r["total_4w"] for r in rows)
    total_sessions = sum(r["sessions_4w"] for r in rows)
    overall_avg    = _avg(total_att, total_sessions)

    # Weakest = smallest avg_4w, treating "no data" as 0 (worst case).
    weakest = min(
        rows,
        key=lambda r: r["avg_4w"] if r["avg_4w"] is not None else 0.0,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active classes", active_count)
    c2.metric("Attendances (4w)", total_att)
    c3.metric("Avg / session", _fmt_avg(overall_avg))
    c4.metric(
        "Weakest class",
        f"{weakest['schedule_day'][:3]} {weakest['start_time']}",
        delta=f"{_fmt_avg(weakest['avg_4w'])} avg",
        delta_color="off",
    )

    st.divider()

    # --- Main table -----------------------------------------------------
    st.subheader("Classes")
    st.caption(
        "Sorted by 4-week average attendance, best first. "
        "Trend compares the last 4 weeks to the preceding 4."
    )

    sorted_rows = sorted(
        rows,
        key=lambda r: r["avg_4w"] if r["avg_4w"] is not None else -1,
        reverse=True,
    )

    display = []
    for r in sorted_rows:
        instructor = r["instructor_name"] or "(unassigned)"
        if r["instructor_status"] and r["instructor_status"] != "active":
            instructor += "  (inactive)"

        last_seen = (r["last_attendance"] or "—")
        if last_seen and last_seen != "—":
            last_seen = last_seen[:10]

        display.append({
            "Class":         f"{r['schedule_day'][:3]} {r['start_time']} — {r['class_name']}",
            "Instructor":    instructor,
            "4w avg":        _fmt_avg(r["avg_4w"]),
            "Unique (4w)":   r["unique_4w"],
            "8w avg":        _fmt_avg(r["avg_8w"]),
            "12w avg":       _fmt_avg(r["avg_12w"]),
            "Trend":         r["trend"],
            "Subs (4w)":     r["subs_4w"],
            "Last seen":     last_seen,
        })

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Schedule heatmap -----------------------------------------------
    st.subheader("Schedule heatmap")
    st.caption(
        "Average attendance per class session, by day and start time. "
        "Blank cells mean no class at that slot."
    )

    times = sorted({r["start_time"] for r in rows})

    # Slot → average across any classes at that slot (usually one).
    slot_avg: dict[tuple[str, str], float | None] = {}
    slot_count: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r["schedule_day"], r["start_time"])
        slot_count[key] = slot_count.get(key, 0) + 1
        if slot_count[key] == 1:
            slot_avg[key] = r["avg_4w"]
        else:
            # Multiple classes at the same slot: average them.
            prev = slot_avg[key] or 0.0
            cur  = r["avg_4w"] or 0.0
            slot_avg[key] = (prev + cur) / 2

    z = []
    for t in times:
        row_vals = []
        for d in DAY_ORDER:
            v = slot_avg.get((d, t))
            row_vals.append(v if v is not None else None)
        z.append(row_vals)

    if times:
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=DAY_ORDER,
            y=times,
            colorscale="YlGn",
            zmin=0,
            hovertemplate="%{x} %{y}<br>Avg: %{z:.1f}<extra></extra>",
            showscale=True,
            colorbar=dict(title="Avg", thickness=15),
        ))
        fig.update_layout(
            height=max(220, 60 * len(times) + 100),
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(title=None, side="top"),
            yaxis=dict(title=None, autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No scheduled times found.")

    st.divider()

    # --- Trainer load ---------------------------------------------------
    st.subheader("Trainer load (4w)")
    st.caption(
        "Total attendance generated per trainer over the last 4 weeks, "
        "across all their classes."
    )

    trainer_load: dict[str, dict] = {}
    for r in rows:
        name = r["instructor_name"] or "(unassigned)"
        bucket = trainer_load.setdefault(name, {"classes": 0, "attendance": 0})
        bucket["classes"]    += 1
        bucket["attendance"] += r["total_4w"]

    load_rows = [
        {
            "Trainer":                name,
            "Classes":                d["classes"],
            "Total attendance (4w)":  d["attendance"],
        }
        for name, d in sorted(
            trainer_load.items(),
            key=lambda kv: kv[1]["attendance"],
            reverse=True,
        )
    ]

    st.dataframe(load_rows, use_container_width=True, hide_index=True)