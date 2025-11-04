import asyncio
from pathlib import Path

from pydantic import BaseModel


class UploadSession:
    def __init__(self, filename: str, file_path: Path, chunk_size: int, total_chunks: int):
        """Class to hold upload session data."""

        self.filename = filename
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.total_chunks = total_chunks
        self.received_chunks: set[int] = set()
        self.lock = asyncio.Lock()


class InitResponse(BaseModel):
    session_id: str
    total_chunks: int


class ChunkResponse(BaseModel):
    progress: float
    is_complete: bool


class FinalizeResponse(BaseModel):
    filename: str
    filepath: str
    file_size: int
    chunks_received: int


class CancelResponse(BaseModel):
    detail: str
