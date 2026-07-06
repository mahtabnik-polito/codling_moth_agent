# Codling Moth Degree-Day Dashboard + Advisory Agent

## What changed

- **Security fix**: DB credentials and host were hardcoded in `app.py`.
  They now come from environment variables (`DB_HOST`, `DB_PORT`, `DB_NAME`,
  `DB_USER`, `DB_PASSWORD`) — see `.env.example`. Rotate the old password,
  since it was committed to disk in plaintext.
- **Extracted shared logic**: all the degree-day / generation-stage logic
  that used to live inline in the `/api/moth_agent/<view_name>` Flask route
  now lives in `moth_advisory_agent/tools.py`, as a standalone function
  `get_codling_moth_status(view_name, end_date)`.
- **New: `moth_advisory_agent/agent.py`** — a Google ADK `Agent` that wraps
  `get_codling_moth_status` as a tool. This is what makes it an
  independent Google Cloud Agent: it can run locally via `adk run`, or be
  deployed to Vertex AI Agent Engine as a managed, autoscaling service with
  its own API endpoint.
- **`deploy_agent.py`** — deploys the agent to Agent Engine.
- **`app.py`**'s existing `/api/moth_agent/<view_name>` route is unchanged
  from the frontend's point of view — it just calls the shared function
  directly (fast, no LLM cost, same JSON shape as before).
- **New: `/api/moth_agent_chat/<view_name>`** (POST) — an optional
  conversational endpoint that forwards free-text questions to the
  *deployed* agent, so it can reason (e.g. "should I still be spraying
  given the forecast?") instead of just returning the fixed report.

## Structure

```
app.py                          Flask web app (dashboard + APIs)
moth_advisory_agent/
  tools.py                      DB access + degree-day/stage logic (shared)
  agent.py                      ADK Agent definition (root_agent)
  requirements.txt
deploy_agent.py                 Deploys agent.py to Vertex AI Agent Engine
.env.example                    Template for required env vars
```

## Running locally

```bash
cp .env.example .env   # fill in real DB credentials
pip install -r requirements.txt -r moth_advisory_agent/requirements.txt --break-system-packages
export $(grep -v '^#' .env | xargs)   # or use python-dotenv / your process manager
python app.py
```

## Testing the agent locally (before deploying)

```bash
export $(grep -v '^#' .env | xargs)
adk run moth_advisory_agent
```

This opens an interactive prompt where you can ask things like
"What's the codling moth status at San Rocco?" and watch it call the tool.

## Deploying to Vertex AI Agent Engine

```bash
gcloud auth application-default login
export $(grep -v '^#' .env | xargs)
python deploy_agent.py
```

Copy the printed resource name into `.env` as `AGENT_ENGINE_RESOURCE_NAME`
so `app.py`'s `/api/moth_agent_chat` route can reach it.

## Notes / things worth deciding next

- `debug=True` was removed from the default `app.run(...)` (it's a code-
  execution risk in production). Set `FLASK_DEBUG=true` locally if you want
  it back.
- The DB credentials get passed to the deployed agent via `env_vars` in
  `deploy_agent.py`. For anything beyond a prototype, move these to
  Secret Manager instead and reference the secret in the deployment config.
- The agent currently connects directly to your Postgres instance's
  private IP (`10.7.18.68`). Agent Engine runs in Google's infrastructure,
  not your network — you'll likely need a VPC connector / Cloud SQL Auth
  Proxy / allowlisted IP so the deployed agent can actually reach the DB.
