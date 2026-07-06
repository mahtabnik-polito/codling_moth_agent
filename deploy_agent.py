"""
One-time (or repeat-on-change) deployment of the Codling Moth Advisory
Agent to Vertex AI Agent Engine.

Usage:
    pip install -r moth_advisory_agent/requirements.txt --break-system-packages
    gcloud auth application-default login
    python deploy_agent.py

After it finishes, copy the printed resource name into your .env as
AGENT_ENGINE_RESOURCE_NAME so app.py can query the deployed agent.
"""

import os

import vertexai
from vertexai import agent_engines
from vertexai.agent_engines import AdkApp

from moth_advisory_agent.agent import root_agent

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ["GOOGLE_CLOUD_STAGING_BUCKET"]

vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING_BUCKET)

app = AdkApp(agent=root_agent)

# Quick local smoke test before deploying (uses your local DB credentials,
# so make sure DB_HOST/DB_USER/DB_PASSWORD etc. are set in your environment).
print("Running local smoke test...")
for event in app.stream_query(
    user_id="local-test-user",
    message="What's the current codling moth status at Laimburg?",
):
    print(event)

print("\nDeploying to Vertex AI Agent Engine (this can take several minutes)...")
remote_app = agent_engines.create(
    agent=app,
    requirements=[
        "google-cloud-aiplatform[agent_engines,adk]",
        "psycopg2-binary",
    ],
    extra_packages=["moth_advisory_agent"],
    # Pass through DB credentials as environment variables available to the
    # deployed agent's runtime. Prefer Secret Manager for production.
    env_vars={
        "DB_HOST": os.environ["DB_HOST"],
        "DB_PORT": os.environ.get("DB_PORT", "5432"),
        "DB_NAME": os.environ["DB_NAME"],
        "DB_USER": os.environ["DB_USER"],
        "DB_PASSWORD": os.environ["DB_PASSWORD"],
    },
)

print("\nDeployed. Resource name:")
print(remote_app.resource_name)
print("\nAdd this to your .env as AGENT_ENGINE_RESOURCE_NAME")
