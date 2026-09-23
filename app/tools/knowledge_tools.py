"""
Agent tools for accessing the internal knowledge base.

The agent supplies only the semantic search query.
tenant_id comes from trusted AppContext and is invisible to the model.

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
    Search the authenticated tenant's internal knowledge base.

    Use this when answering questions that require company or application
    knowledge not available from the user's message.
    """

    if not context.context.has_permission(KNOWLEDGE_READ):
        return "Permission denied."

    results = await retrieve_knowledge(
        tenant_id=context.context.tenant_id,
        query=query,
    )

    if not results:
        return "No relevant internal knowledge was found."

    return "\n\n".join(
        (
            f"[Source: {result.filename}, chunk {result.chunk_index}, "
            f"distance {result.distance:.3f}]\n"
            f"{result.content}"
        )
        for result in results
    )
