import os

from flask import Flask, render_template, jsonify, request

from moth_advisory_agent.tools import (
    get_db_connection,
    get_codling_moth_status,
    ALLOWED_VIEWS,
    STATION_LABELS,
)

app = Flask(__name__)

# --- Optional: connection to the deployed Vertex AI Agent Engine -------
# Only needed for the conversational /api/moth_agent_chat endpoint below.
# If AGENT_ENGINE_RESOURCE_NAME isn't set, that endpoint just returns a
# clear error instead of crashing the whole app.
_remote_agent = None


def get_remote_agent():
    global _remote_agent
    if _remote_agent is not None:
        return _remote_agent

    resource_name = os.environ.get("AGENT_ENGINE_RESOURCE_NAME")
    if not resource_name:
        return None

    import vertexai

    client = vertexai.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
    _remote_agent = client.agent_engines.get(name=resource_name)
    return _remote_agent


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/views')
def get_views():
    views_list = [{"id": view_id, "name": name} for view_id, name in STATION_LABELS.items()]
    return jsonify(views_list)


@app.route('/api/data/<view_name>')
def get_view_data(view_name):
    if view_name not in ALLOWED_VIEWS:
        return jsonify({"error": "Invalid view name"}), 400

    start_date = request.args.get('start_date', '2025-05-16')
    end_date = request.args.get('end_date', '2026-07-06')
    aggregate = request.args.get('aggregate', 'daily')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if aggregate == 'hourly':
            query = f"""
                SELECT
                    time,
                    hour_temp,
                    hour_humidity,
                    hour_hdd
                FROM {view_name}
                WHERE time BETWEEN %s AND %s
                ORDER BY time ASC;
            """
        else:
            query = f"""
                SELECT
                    date_trunc('day', time) AS time,
                    ROUND(AVG(hour_temp)::numeric, 2) AS avg_temp,
                    ROUND(AVG(hour_humidity)::numeric, 2) AS avg_humidity,
                    ROUND(SUM(hour_hdd)::numeric, 2) AS sum_hdd
                FROM {view_name}
                WHERE time BETWEEN %s AND %s
                GROUP BY 1
                ORDER BY 1 ASC;
            """

        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        summary_query = f"""
            SELECT
                ROUND(AVG(hour_temp)::numeric, 2) AS avg_temp,
                ROUND(AVG(hour_humidity)::numeric, 2) AS avg_humidity,
                ROUND(SUM(hour_hdd)::numeric, 2) AS total_hdd
            FROM {view_name}
            WHERE time BETWEEN %s AND %s;
        """
        cursor.execute(summary_query, (start_date, end_date))
        summary = cursor.fetchone()

        cursor.close()
        conn.close()

        for row in rows:
            if hasattr(row['time'], 'isoformat'):
                row['time'] = row['time'].isoformat()

        return jsonify({
            "data": rows,
            "summary": summary
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cumulative/<view_name>')
def get_cumulative_data(view_name):
    if view_name not in ALLOWED_VIEWS:
        return jsonify({"error": "Invalid view name"}), 400

    start_date = request.args.get('start_date', '2025-05-16')
    end_date = request.args.get('end_date', '2026-07-06')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

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
            WHERE time BETWEEN %s AND %s
            ORDER BY time ASC;
        """

        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        for row in rows:
            if hasattr(row['time'], 'isoformat'):
                row['time'] = row['time'].isoformat()

        return jsonify(rows)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/moth_agent/<view_name>')
def get_moth_agent_report(view_name):
    """Structured advisory report, computed locally (no LLM call).

    This preserves the existing frontend contract exactly, just backed by
    the shared tool function instead of duplicated logic.
    """
    end_date = request.args.get('end_date', '2026-07-06')
    result = get_codling_moth_status(view_name=view_name, end_date=end_date)

    if "error" in result and len(result) == 1:
        status = 400 if "Invalid view name" in result["error"] else 500
        return jsonify(result), status

    return jsonify(result)


@app.route('/api/moth_agent_chat/<view_name>', methods=['POST'])
def moth_agent_chat(view_name):
    """Conversational endpoint backed by the deployed Vertex AI agent.

    Lets the agent reason over the user's free-text question (e.g. "should
    I still be spraying?") rather than just returning the fixed report.
    Requires AGENT_ENGINE_RESOURCE_NAME to be set (see deploy_agent.py).
    """
    remote_agent = get_remote_agent()
    if remote_agent is None:
        return jsonify({
            "error": "No deployed agent configured. Run deploy_agent.py and "
                     "set AGENT_ENGINE_RESOURCE_NAME."
        }), 503

    body = request.get_json(silent=True) or {}
    user_message = body.get('message', f"What's the current status at {view_name}?")
    user_id = body.get('user_id', 'anonymous')

    events = list(remote_agent.stream_query(user_id=user_id, message=user_message))
    return jsonify({"events": events})


if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
