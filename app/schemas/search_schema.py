from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResultChunk(BaseModel):
    file_path: str
    content: str
    start_line: int
    end_line: int
    symbol_name: str | None = None


class SearchResponse(BaseModel):
    answer: str
    sources: list[SearchResultChunk]
    cached: bool = False