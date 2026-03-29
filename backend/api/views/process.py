import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..models.process import ProcessRequest, ProcessResponse, ProcessStatusResponse
from ..services import process

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("/")
async def process_ties(request: ProcessRequest) -> ProcessResponse:
    """Run TIE detector on uploaded files."""

    logger.info(f"Processing TIE detection for session {request.session_id}")
    return await process.process_ties(request)


@router.get("/{session_id}/status")
async def get_status(session_id: str) -> ProcessStatusResponse:
    """Get the status and results of TIE detection for a session."""

    logger.info(f"Getting process status for session {session_id}")
    return await process.get_process_results(session_id)


@router.get("/{session_id}/logs")
async def get_logs(session_id: str) -> dict[str, str]:
    """Get the container logs for a processing session."""

    logger.info(f"Getting logs for session {session_id}")
    return await process.get_container_logs(session_id)


@router.get("/{session_id}/files/{filename}")
async def download_file(session_id: str, filename: str) -> FileResponse:
    """Download an output file from a processing session."""

    file_path = process.get_output_file(session_id, filename)
    return FileResponse(path=file_path, filename=filename)
