from pydantic import BaseModel
from uuid import UUID


class RepoIngestRequest(BaseModel):
    repo_url: str


class RepoIngestResponse(BaseModel):
    repo_id: UUID
    status: str


class RepoStatusResponse(BaseModel):
    repo_id: UUID
    status: str
    error_message: str | None = None