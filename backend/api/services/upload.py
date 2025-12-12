import logging
import math
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile

from ..config import config
from ..models.upload import (
    InitResponse,
    UploadResponse,
)

UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024
upload_dir_path = Path(config.UPLOAD_DIR_PATH)
upload_dir_path.mkdir(exist_ok=True)


logger = logging.getLogger("uvicorn.error")


async def init_upload() -> InitResponse:
    """Initialize a new upload session (a directory with multiple uploaded files)."""

    while True:
        session_id = str(uuid.uuid4())
        session_dir = upload_dir_path / session_id
        try:
            session_dir.mkdir()
            break
        except FileExistsError:
            continue

    return InitResponse(
        session_id=session_id,
    )


async def upload_file(session_id: str, filename: str, upload_file: UploadFile) -> UploadResponse:
    """Receive a file."""

    session_dir = upload_dir_path / session_id

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session id not found")

    try:
        file_path = session_dir / filename
        async with aiofiles.open(file_path, "wb") as out_file:
            while content := await upload_file.read(UPLOAD_CHUNK_SIZE):
                await out_file.write(content)

        logger.info(f"Uploaded file {file_path} ({os.path.getsize(file_path)} bytes)")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return UploadResponse(status="File uploaded successfully")
