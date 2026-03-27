import logging

from fastapi import APIRouter, UploadFile

from ..models.upload import (
    InitResponse,
    UploadResponse,
)
from ..services import upload

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("/init")
async def init_session() -> InitResponse:
    """Initialize a new upload session (a directory with multiple uploaded files)."""

    logger.info("Initializing new upload session.")
    return await upload.init_upload()


@router.post("/")
async def upload_file(session_id: str, filename: str, file: UploadFile) -> UploadResponse:
    """Receive a file."""

    logger.info(f"Receiving file {filename} for session {session_id}.")
    return await upload.upload_file(session_id, filename, file)


@router.get("/{session_id}/files")
async def list_files(session_id: str) -> dict[str, list[str]]:
    """List all uploaded files in a session."""

    logger.info(f"Listing files for session {session_id}")
    return await upload.list_session_files(session_id)
