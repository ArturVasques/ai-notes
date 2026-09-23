"""
Agent tools for searching the authenticated user's notes.

The agent supplies only the semantic search query.
user_id comes from trusted AppContext and is invisible to the model.

Used by:
- assistant agent.
- specialist agents requiring internal knowledge.
"""

from agents import RunContextWrapper, function_tool

from app.auth.context import AppContext
from app.auth.permissions import KNOWLEDGE_READ
from app.services.rag.retrieval_service import retrieve_knowledge


@function_tool
async def search_knowledge(
    context: RunContextWrapper[AppContext],
    query: str,
) -> str:
    """
    Search the authenticated user's notes.

    Use this when answering questions that require knowledge from the user's
    notes that is not available from the user's message.
    """

    if not context.context.has_permission(KNOWLEDGE_READ):
        return "Permission denied."

    results = await retrieve_knowledge(
        user_id=context.context.user_id,
        query=query,
    )

    if not results:
        return "No relevant notes were found."

    return "\n\n".join(
        (
            f"[Source: {result.title}, chunk {result.chunk_index}, "
            f"distance {result.distance:.3f}]\n"
            f"{result.content}"
        )
        for result in results
    )
