"""
HTTP input contract for AI chat operations.

Used by:
- api/chat.py
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """User request sent to the AI assistant."""

    message: str = Field(
        min_length=1,
        max_length=10_000,
    )
