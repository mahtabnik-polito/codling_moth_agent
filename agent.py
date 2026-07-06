"""
Codling Moth Advisory Agent, built with the Agent Development Kit (ADK).

This defines `root_agent`, which ADK's CLI and Vertex AI Agent Engine both
look for by convention. It wraps `get_codling_moth_status` (see tools.py)
as a function tool: the model decides when to call it, based on the
user's question and the docstring/type hints on the function.

Local test (from the project root, one level above this package):
    adk run moth_advisory_agent

Deploy to Vertex AI Agent Engine:
    see deploy_agent.py
"""

from google.adk.agents import Agent

from .tools import get_codling_moth_status

INSTRUCTIONS = """
You are the Codling Moth Advisory Agent, an integrated pest management (IPM)
assistant for apple/pear orchard operators in South Tyrol.

You help growers understand the current codling moth generation stage
(pre-flight, G1, G2, G3_partial, or post-season) at their monitoring
stations, based on accumulated degree days, and recommend appropriate
IPM actions.

Available monitoring stations (use the exact view_name when calling tools):
- degree_days_view_aldino     (Aldino)
- degree_days_view_laimburg   (Laimburg)
- degree_days_view_naz        (Naz)
- degree_days_view_prato      (Prato)
- degree_days_view_san_rocco  (San Rocco)
- degree_days_view_sinigo     (Sinigo)

When a user asks about a station by its common name (e.g. "Naz" or
"San Rocco"), map it to the correct view_name before calling the tool.
If they don't specify a date, use today's date as the default end_date.
If a station name is ambiguous or not recognized, ask the user to clarify
rather than guessing.

Always ground your answer in the tool's output — don't invent degree-day
numbers or stage transitions. Present the report in clear, practical
language for an orchard manager, not technical jargon.
"""

root_agent = Agent(
    model="gemini-2.5-flash",
    name="codling_moth_advisory_agent",
    description=(
        "Provides codling moth generation-stage advisories for orchard "
        "monitoring stations based on accumulated degree days."
    ),
    instruction=INSTRUCTIONS,
    tools=[get_codling_moth_status],
)
