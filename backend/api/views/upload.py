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
