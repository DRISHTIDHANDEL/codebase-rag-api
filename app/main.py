from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from app.config import settings
from app.db.session import get_db, engine
from app.db.base import Base
from app.db.models import Repository, RepoStatus
from app.schemas.repo_schema import RepoIngestRequest, RepoIngestResponse, RepoStatusResponse
from app.schemas.search_schema import SearchRequest, SearchResponse, SearchResultChunk
from app.workers.tasks import process_repository_task
from app.services.retrieval import hybrid_search
from app.core.cache import make_query_hash, get_cached_response, set_cached_response

app = FastAPI(title=settings.APP_NAME)


@app.post("/api/v1/repos/ingest", response_model=RepoIngestResponse)
def ingest_repo(payload: RepoIngestRequest, db: Session = Depends(get_db)):
    existing = db.query(Repository).filter(Repository.repo_url == payload.repo_url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Repository already ingested")

    repo = Repository(id=uuid4(), repo_url=payload.repo_url, status=RepoStatus.PENDING)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    process_repository_task.delay(repo_url=payload.repo_url, repo_id=str(repo.id))

    return RepoIngestResponse(repo_id=repo.id, status=repo.status.value)


@app.get("/api/v1/repos/{repo_id}/status", response_model=RepoStatusResponse)
def get_repo_status(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    return RepoStatusResponse(
        repo_id=repo.id,
        status=repo.status.value,
        error_message=repo.error_message,
    )


@app.post("/api/v1/repos/{repo_id}/search", response_model=SearchResponse)
def search_repo(repo_id: str, payload: SearchRequest, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != RepoStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Repository status is {repo.status.value}, not ready for search")

    # 1. Check Redis cache first
    cache_key = make_query_hash(repo_id, payload.query)
    cached = get_cached_response(cache_key)
    if cached:
        return SearchResponse(**cached, cached=True)

    # 2. Hybrid retrieval
    results = hybrid_search(db, repo_id, payload.query, top_k=payload.top_k)

    if not results:
        response_data = {
            "answer": "No relevant code found for this query.",
            "sources": [],
        }
        set_cached_response(cache_key, response_data)
        return SearchResponse(**response_data, cached=False)

    # 3. Build a simple answer citing sources (LLM call kept minimal/optional here)
    context_snippets = "\n\n".join(
        f"File: {r['file_path']} (lines {r['start_line']}-{r['end_line']})\n{r['content'][:300]}"
        for r in results
    )
    answer = (
        f"Found {len(results)} relevant code section(s) for your query. "
        f"Top match: {results[0]['file_path']} (lines {results[0]['start_line']}-{results[0]['end_line']})."
    )

    response_data = {
        "answer": answer,
        "sources": [SearchResultChunk(**r).model_dump() for r in results],
    }

    # 4. Cache it
    set_cached_response(cache_key, response_data)

    return SearchResponse(**response_data, cached=False)


@app.get("/health")
def health_check():
    return {"status": "ok"}