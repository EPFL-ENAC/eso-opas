import math
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile

from ..config import config
from ..models.upload import (
    CancelResponse,
    ChunkResponse,
    FinalizeResponse,
    InitResponse,
    UploadSession,
)

upload_sessions: dict[str, UploadSession] = {}
upload_dir_path = Path(config.UPLOAD_DIR_PATH)
upload_dir_path.mkdir(exist_ok=True)


async def init_upload(filename: str, file_size: int, chunk_size: int) -> InitResponse:
    """Initialize a new upload session."""

    session_id = str(uuid.uuid4())
    file_path = upload_dir_path / f"{session_id}_{filename}"
    total_chunks = math.ceil(file_size / chunk_size)

    upload_sessions[session_id] = UploadSession(
        filename=filename, file_path=file_path, chunk_size=chunk_size, total_chunks=total_chunks
    )

    async with aiofiles.open(file_path, "w+b") as f:
        await f.seek(file_size - 1)
        await f.write(b"\0")

    return InitResponse(
        session_id=session_id,
        total_chunks=total_chunks,
    )


async def upload_chunk(session_id: str, chunk_index: int, file: UploadFile) -> ChunkResponse:
    """Receive and process a single chunk."""

    if session_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Session id not found")

    session = upload_sessions[session_id]
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise HTTPException(status_code=400, detail="Invalid chunk index")

    try:
        chunk_data = await file.read()
        offset = chunk_index * session.chunk_size

        async with session.lock:
            async with aiofiles.open(session.file_path, "r+b") as f:
                await f.seek(offset)
                await f.write(chunk_data)

            session.received_chunks.add(chunk_index)

        is_complete = len(session.received_chunks) == session.total_chunks

        return ChunkResponse(
            progress=len(session.received_chunks) / session.total_chunks,
            is_complete=is_complete,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def finalize_upload(session_id: str) -> FinalizeResponse:
    """Finalize the upload and clean up."""

    if session_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Session id not found")

    session = upload_sessions[session_id]

    if len(session.received_chunks) != session.total_chunks:
        missing = session.total_chunks - len(session.received_chunks)
        raise HTTPException(status_code=400, detail=f"Upload incomplete. Missing {missing} chunks. Aborting finalize.")

    file_size = os.path.getsize(session.file_path)
    del upload_sessions[session_id]

    return FinalizeResponse(
        filename=session.filename,
        filepath=str(session.file_path),
        file_size=file_size,
        chunks_received=len(session.received_chunks),
    )


async def cancel_upload(session_id: str) -> CancelResponse:
    """Cancel an upload and clean up"""

    if session_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Session id not found")

    session = upload_sessions[session_id]

    if session.file_path.exists():
        os.remove(session.file_path)

    del upload_sessions[session_id]

    return CancelResponse(detail="Upload canceled and cleaned up")
