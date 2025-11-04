import logging

from fastapi import APIRouter, Header, UploadFile

from ..models.upload import (
    CancelResponse,
    ChunkResponse,
    FinalizeResponse,
    InitResponse,
)
from ..services import upload

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("/init")
async def init_upload(filename: str, file_size: int, chunk_size: int) -> InitResponse:
    """Initialize a new upload session."""

    logger.info(f"Initializing upload for file: {filename}, size: {file_size}, chunk size: {chunk_size}.")
    return await upload.init_upload(filename, file_size, chunk_size)


@router.post("/chunk/{session_id}")
async def upload_chunk(session_id: str, chunk_index: int, file: UploadFile) -> ChunkResponse:
    """Receive and process a single chunk."""

    logger.info(f"Receiving uploaded chunk {chunk_index} for session {session_id}.")
    return await upload.upload_chunk(session_id, chunk_index, file)


@router.post("/finalize/{session_id}")
async def finalize_upload(session_id: str) -> FinalizeResponse:
    """Finalize the upload and clean up."""

    logger.info(f"Finalizing upload for session {session_id}.")
    return await upload.finalize_upload(session_id)


@router.delete("/cancel/{session_id}")
async def cancel_upload(session_id: str) -> CancelResponse:
    """Cancel an upload and clean up"""

    logger.info(f"Cancelling upload for session {session_id}.")
    return await upload.cancel_upload(session_id)
