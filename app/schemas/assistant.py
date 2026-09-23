"""
Structured output contract for the main AI assistant.

The agent returns a predictable application contract instead of arbitrary
text or JSON serialized inside another string.

Used by:
- assistant agent as its output_type.
- agent service.
- HTTP chat API.
"""

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """Knowledge source referenced by an assistant answer."""

    filename: str
    chunk_index: int


class AssistantResponse(BaseModel):
    """Structured final response produced by the main assistant."""

    answer: str = Field(description="Final answer presented to the user.")

    sources: list[SourceReference] = Field(
        default_factory=list,
        description="Internal knowledge sources supporting the answer.",
    )
