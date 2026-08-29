# Codebase RAG & Architecture Search API

I built this to answer a question I kept running into at work: when you're dropped into a large unfamiliar codebase, how do you actually find where something is handled without grepping for 20 minutes? This is a backend service that ingests a GitHub repo, breaks it into meaningful chunks (actual functions/classes, not just arbitrary lines), embeds them, and lets you ask natural language questions about the codebase and get back the relevant code with file paths and line numbers.

## What it does

1. You give it a GitHub URL
2. It clones the repo, walks every Python file, and uses Python's `ast` module to pull out individual functions, classes and imports as separate chunks (with a simpler line-based fallback for non-Python files)
3. Each chunk gets embedded and stored in Postgres with pgvector
4. You ask a question in plain English, it runs both a vector similarity search and a keyword search, combines the results with Reciprocal Rank Fusion, and returns the top matches
5. Repeated queries get served from Redis instead of hitting the DB again

Ingestion happens in the background via Celery since cloning + parsing + embedding a real repo can take a minute or two — you don't want the API request hanging that long.

## Stack

- FastAPI for the API layer
- Postgres 16 + pgvector for storage and vector search
- SQLAlchemy + Alembic for the ORM/migrations
- Celery + Redis for the async ingestion pipeline and query caching
- sentence-transformers (`all-MiniLM-L6-v2`) for embeddings — runs locally, no API key needed. Swappable for OpenAI's embedding models if you want higher quality and don't mind the cost
- Docker/Docker Compose to run Postgres + Redis

## Layout

```
app/
  main.py            -> the 3 endpoints
  config.py          -> env config
  db/
    models.py        -> Repository, CodeChunk, QueryCache tables
    session.py
  services/
    parser.py        -> the AST chunking logic, this is the core of the project
    embeddings.py
    retrieval.py      -> hybrid search + RRF
  workers/
    celery_app.py
    tasks.py           -> the actual ingestion pipeline
  schemas/
  core/
    cache.py
alembic/
docker-compose.yml
```

## Endpoints

- `POST /api/v1/repos/ingest` — give it `{"repo_url": "..."}`, kicks off ingestion, returns a repo id
- `GET /api/v1/repos/{id}/status` — PENDING / PROCESSING / COMPLETED / FAILED
- `POST /api/v1/repos/{id}/search` — `{"query": "...", "top_k": 5}`, returns matched chunks with file/line info

## Running it

Spin up Postgres and Redis:
```bash
docker-compose up -d db redis
docker exec -it rag_postgres psql -U raguser -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Install deps and run migrations:
```bash
pip install -r requirements.txt
alembic upgrade head
```

Run the API:
```bash
python -m uvicorn app.main:app --reload
```

And in a separate terminal, the worker (needs `--pool=solo` on Windows, Celery's default pool doesn't play well there):
```bash
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

Then hit `http://127.0.0.1:8000/docs`, ingest something like `https://github.com/psf/requests`, wait for it to hit COMPLETED, and start searching.

## A few things worth knowing if you're reading the code

- The parser only handles Python well right now — everything else falls back to chunking every 50 lines, which is obviously not as good. Adding tree-sitter for JS/TS would be the next step if I kept going.
- Embeddings dimension is 384 because I'm using the local MiniLM model instead of OpenAI (which would be 1536) — if you swap providers you'll need a new migration for the `embedding` column.
- The "LLM answer" in `/search` right now is a templated string over the top matches, not an actual LLM call — didn't want to require an OpenAI key just to run this locally. Wiring in a real chat completion over the retrieved context would be a small addition to `main.py`.
- `depth=1` on the git clone so we're not pulling full history, just the latest snapshot — fine for search, wouldn't be enough if you needed blame/history info later.
