"""
HTTP API for AI assistant interactions.

Responsibilities:
- validate HTTP input.
- obtain trusted AppContext from the authentication boundary.
- execute the assistant application service.
- return the structured application contract.

Agent implementation details remain outside the HTTP layer.
"""

from fastapi import APIRouter, Depends

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.schemas.assistant import AssistantResponse
from app.schemas.chat import ChatRequest
from app.services.ai.agent_service import run_assistant

router = APIRouter(
    prefix="/chat",
    tags=["AI"],
)


@router.post("", response_model=AssistantResponse)
async def chat(
    request: ChatRequest,
    context: AppContext = Depends(get_app_context),
) -> AssistantResponse:
    """Execute the AI assistant for the authenticated caller."""

    return await run_assistant(
        message=request.message,
        context=context,
    )
