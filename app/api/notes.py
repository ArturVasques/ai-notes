"""
HTTP API for notes.

Identity always comes from AppContext rather than request parameters: a note
is owned by the authenticated user who creates it.

Current implementation ingests notes synchronously within the request.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.context import AppContext
from app.auth.dependencies import get_app_context
from app.auth.permissions import NOTES_CREATE
from app.schemas.note import NoteCreateRequest, NoteCreateResponse
from app.services.notes.ingestion_service import ingest_note

router = APIRouter(
    prefix="/notes",
    tags=["Notes"],
)


@router.post(
    "",
    response_model=NoteCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    request: NoteCreateRequest,
    context: AppContext = Depends(get_app_context),
) -> NoteCreateResponse:
    """Create a note owned by the authenticated user."""

    if not context.has_permission(NOTES_CREATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    note_id = await ingest_note(
        created_by=context.user_id,
        title=request.title,
        content=request.content,
    )

    return NoteCreateResponse(note_id=note_id)
