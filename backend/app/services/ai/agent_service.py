"""
Application service responsible for executing AI agents.

This module is the boundary between application code and the Agents SDK.

Used by:
- chat HTTP API.
- future background or event-driven AI workflows.
"""

from agents import Runner

import app.core.openai  # noqa: F401
from app.agents.assistant import assistant_agent
from app.auth.context import AppContext
from app.schemas.assistant import AssistantResponse


class AssistantContractError(Exception):
    """
    Raised when the agent's structured output does not match the declared
    contract (AssistantResponse).

    Kept as its own exception type (rather than a bare TypeError) so
    app/api/errors.py can map exactly this failure to a 502, without also
    catching unrelated TypeErrors raised elsewhere in the request path.
    """


async def run_assistant(
    *,
    message: str,
    context: AppContext,
) -> AssistantResponse:
    """Execute the main assistant with trusted application context."""

    result = await Runner.run(
        assistant_agent,
        message,
        context=context,
    )

    output = result.final_output

    if not isinstance(output, AssistantResponse):
        raise AssistantContractError("Assistant returned an unexpected output type")

    return output
