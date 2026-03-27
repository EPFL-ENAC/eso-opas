from pydantic import BaseModel


class ProcessRequest(BaseModel):
    session_id: str
    corner_max_n_corners: int = 100
    ransac_iterations: int = 200
    ransac_threshold: int = 10
    lines_starts: dict[str, int] | None = None
    lines_ends: dict[str, int] | None = None


class ProcessResponse(BaseModel):
    status: str
    message: str


class ProcessStatusResponse(BaseModel):
    status: str
    message: str
    output_files: list[str] | None = None
    progress_step: int | None = None
    progress_total: int | None = None
    progress_message: str | None = None
