from pydantic import BaseModel


class InitResponse(BaseModel):
    session_id: str


class UploadResponse(BaseModel):
    status: str
