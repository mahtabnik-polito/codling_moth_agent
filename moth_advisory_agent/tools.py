"""
Shared business logic for the Codling Moth Advisory Agent.

This module is intentionally framework-agnostic: the same
`get_codling_moth_status` function is used
  1) directly by the Flask app (app.py) for the existing /api/moth_agent
     JSON endpoint, and
  2) as an ADK "function tool" by the Vertex AI agent defined in agent.py.

Keeping the logic here (rather than duplicated in both places) means the
agent and the web app can never drift out of sync.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# --- Database connection -----------------------------------------------
# Credentials now come from environment variables instead of being
# hardcoded. Set these in your shell, a .env file (loaded by your process
# manager), or as Secret Manager-backed env vars when deployed.
#
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def get_db_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        cursor_factory=RealDictCursor,
    )


# Whitelist of allowed views to prevent SQL injection
ALLOWED_VIEWS = {
    "degree_days_view_aldino",
    "degree_days_view_laimburg",
    "degree_days_view_naz",
    "degree_days_view_prato",
    "degree_days_view_san_rocco",
    "degree_days_view_sinigo",
}

STATION_LABELS = {
    "degree_days_view_aldino": "Aldino",
    "degree_days_view_laimburg": "Laimburg",
    "degree_days_view_naz": "Naz",
    "degree_days_view_prato": "Prato",
    "degree_days_view_san_rocco": "San Rocco",
    "degree_days_view_sinigo": "Sinigo",
}

STAGE_INFO = {
    "pre-flight": {
        "title": "Pre-Flight Stage",
        "badge_class": "badge-preflight",
        "desc": "Overwintering larvae are pupating and preparing to emerge as adult moths. No egg-laying is active yet.",
        "action": "Deploy pheromone traps in the orchard canopy to capture the first adult males and establish the 'biofix' date.",
    },
    "G1": {
        "title": "First Generation (G1)",
        "badge_class": "badge-g1",
        "desc": "Adult moths are flying, mating, and laying eggs. First generation larvae are beginning to hatch and enter developing fruit.",
        "action": "This is a critical treatment window. Target emerging G1 larvae with appropriate ovicides or larvicides based on biofix trap catches.",
    },
    "G2": {
        "title": "Second Generation (G2)",
        "badge_class": "badge-g2",
        "desc": "Second generation flight is active. Significant egg-laying is underway, leading to a major crop damage risk.",
        "action": "Apply targeted spray treatments based on degree day accumulation to prevent larvae from boring into maturing apples/pears.",
    },
    "G3_partial": {
        "title": "Third Generation Partial (G3)",
        "badge_class": "badge-g3",
        "desc": "Warm weather has triggered a partial third flight. Late-season larvae are active, risking damage to late-harvest cultivars.",
        "action": "Conduct visual inspections of late-season fruit. Maintain coverage on late-harvest varieties if trap counts remain elevated.",
    },
    "post-season": {
        "title": "Post-Season / Diapause",
        "badge_class": "badge-postseason",
        "desc": "Temperatures are cooling down or the season has wrapped up. Larvae are spinning silken cocoons to overwinter.",
        "action": "No chemical treatments required. Implement orchard hygiene: remove fallen fruit, clean bins, and remove wooden debris.",
    },
    "unknown": {
        "title": "Unknown Stage",
        "badge_class": "badge-unknown",
        "desc": "Insufficient degree days data to classify development.",
        "action": "Ensure temperature monitoring station is active and database tables are updating.",
    },
}


def assign_generation(dd):
    if dd is None:
        return "unknown"
    if dd < 250:
        return "pre-flight"
    elif dd < 850:
        return "G1"
    elif dd < 1600:
        return "G2"
    elif dd < 2000:
        return "G3_partial"
    else:
        return "post-season"


def get_codling_moth_status(view_name: str, end_date: str = "2026-07-06") -> dict:
    """Get the codling moth generation stage and advisory for one orchard station.

    Computes cumulative degree days (DD) from the start of the monitoring
    record up through end_date, classifies the current codling moth
    development stage (pre-flight, G1, G2, G3_partial, or post-season),
    and returns a biological status summary plus a recommended IPM action.

    Args:
        view_name: The database view/station identifier. Must be one of:
            "degree_days_view_aldino", "degree_days_view_laimburg",
            "degree_days_view_naz", "degree_days_view_prato",
            "degree_days_view_san_rocco", "degree_days_view_sinigo".
        end_date: The date (YYYY-MM-DD) to evaluate the status as of.
            Defaults to "2026-07-06".

    Returns:
        A dictionary with keys: current_stage, current_stage_title,
        current_dd, transitions, report, details, error. On failure,
        "error" is set and other fields are omitted or empty.
    """
    if view_name not in ALLOWED_VIEWS:
        return {"error": f"Invalid view name: {view_name}"}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Cumulative degree days from the very beginning of the record,
        # so generation transitions are computed correctly, but only up
        # to end_date so we report status as of that date.
        query = f"""
            SELECT
                time AS "time",
                SUM(hour_hdd) OVER (ORDER BY time) AS "cumulative_degree_days"
            FROM (
                SELECT
                    date_trunc('day', time)    AS time,
                    SUM(hour_hdd) / 24         AS hour_hdd
                FROM {view_name}
                WHERE time >= (SELECT MIN(time) FROM {view_name})
                GROUP BY 1
            ) daily
            WHERE time <= %s
            ORDER BY time ASC;
        """

        cursor.execute(query, (end_date,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not rows:
            return {
                "current_stage": "unknown",
                "current_dd": 0,
                "transitions": [],
                "report": "No temperature or degree day records found for the selected period.",
            }

        transitions = []
        current_stage = None

        for row in rows:
            time_val = row["time"]
            dd_val = float(row["cumulative_degree_days"]) if row["cumulative_degree_days"] is not None else 0.0
            stage = assign_generation(dd_val)

            if stage != current_stage:
                transitions.append(
                    {
                        "stage": stage,
                        "date": time_val.strftime("%Y-%m-%d") if hasattr(time_val, "strftime") else str(time_val),
                        "dd": round(dd_val, 2),
                    }
                )
                current_stage = stage

        last_row = rows[-1]
        final_dd = float(last_row["cumulative_degree_days"]) if last_row["cumulative_degree_days"] is not None else 0.0
        final_stage = assign_generation(final_dd)
        final_date_str = (
            last_row["time"].strftime("%Y-%m-%d") if hasattr(last_row["time"], "strftime") else str(last_row["time"])
        )

        info = STAGE_INFO.get(final_stage, STAGE_INFO["unknown"])
        station_name = STATION_LABELS.get(view_name, view_name.replace("degree_days_view_", "").replace("_", " ").title())

        report_text = (
            f"Hello, I am your Codling Moth Advisory Agent. Here is my assessment for {station_name} "
            f"as of {final_date_str}:\n\n"
            f"The current Cumulative Degree Days sum is {final_dd:.2f} DD, indicating the codling moth "
            f"population is in the {info['title']} stage.\n\n"
            f"Biological Status: {info['desc']}\n\n"
            f"Recommended Action: {info['action']}"
        )

        return {
            "current_stage": final_stage,
            "current_stage_title": info["title"],
            "current_dd": final_dd,
            "transitions": transitions,
            "report": report_text,
            "details": info,
        }

    except Exception as e:
        return {"error": str(e)}
