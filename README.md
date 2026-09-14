Rag & Architecture Search API

I made this to solve a problem I kept seeing at work: when you’re thrown into a big unknown codebase how do you actually find where something is handled without spending twenty minutes searching through files? This is a backend service that takes a GitHub repo splits it into pieces—like functions and classes—not just random lines of code. It then creates embeddings for each piece. Stores them in a database. You can ask questions in English about the codebase and it returns the most relevant code along with file paths and line numbers.

What it does

You give it a GitHub URL

It clones the repository goes through every Python file and uses Python’s ast module to extract functions, classes and imports as separate chunks. For -Python files it falls back to splitting by lines every 50 lines or so.

Each chunk gets turned into an embedding. Saved in Postgres using pgvector.

When you ask a question in language the system runs both a vector similarity search and a keyword-based search. It combines the results using Reciprocal Rank Fusion to rank them

The top matches are returned with details like which file and what line number they come from.

Repeated queries are served from Redis of going back to the database again.

Ingestion happens in the background using Celery because cloning, parsing and embedding a repo can take a minute or two. You don’t want your API request to hang while that happens.

Stack

FastAPI – for the API layer

Postgres 16 + pgvector – for storage and vector searches

SQLAlchemy + Alembic – for working with the database and managing migrations

Celery + Redis – for running ingestion tasks caching query results

sentence-transformers (all-MiniLM-L6-v2) – for generating embeddings locally no API key needed

You could swap this out for OpenAI models if you want better quality and don't mind paying for it

Docker and Docker Compose – to run Postgres and Redis easily

Layout

app/

main.py            → contains three endpoints

config.py          → handles environment variables

db/

models.py        → defines Repository, CodeChunk QueryCache tables

session.py       → sets up database sessions

services/

parser.py        → uses AST to break code into meaningful chunks. This is the core of the project

embeddings.py

retrieval.py     → handles hybrid search and Reciprocal Rank Fusion

workers/

celery_app.py

tasks.py         → contains the actual ingestion logic

schemas/

core/

cache.py         → manages Redis caching

alembic/

docker-compose.yml

Endpoints

POST /api/v1/repos/ingest – send {"repo_url": "..."} and it starts ingesting the repo returning a unique ID

GET /api/v1/repos/{id}/status – check if the ingestion is PENDING, PROCESSING, COMPLETED or FAILED

POST /api/v1/repos/{id}/search – send {"query": "..." "top_k": 5} and get back matching code chunks with file and line info

Running it

Start Postgres and Redis:

docker-compose up -d db redis

Then connect to the database and enable the vector extension:

docker exec -it rag_postgres psql -U raguser -d rag_db -c " EXTENSION IF NOT EXISTS vector;"

Install dependencies and apply migrations:

pip install -r requirements.txt

alembic upgrade head

Run the API server:

python -m uvicorn app.main:app --reload

In another terminal start the worker process (use --pool=solo on Windows since Celerys default pool doesn’t work well there):

celery -A app.workers.celery_app worker --loglevel=info --pool=solo

Live deployment attempted on Hugging Face Spaces but hit a platform-side quota issue,the code is fully functional locally, see README for setup steps.

Try ingesting a repo like https://github.com/psf/requests

Wait until the status shows COMPLETED

Then begin searching

A things worth knowing if you're looking at the code

The parser only works well with Python right now. All other languages fall back to chunking every 50 lines, which's n’t ideal. Adding tree-sitter support for JavaScript and TypeScript would be the step.

Embedding dimension is 384 because the local MiniLM model produces vectors of that size. If you switch to OpenAI the embeddings will be 1536 dimensions so you’d need a migration to change the column.

Now the "LLM answer" in the search endpoint is just a templated string based on the top results. It’s not calling a LLM. That was intentional. I didn’t want to require an OpenAI key to run this locally. Adding a chat completion using the retrieved context would be a small update, to main.py.

Git is cloned with `depth=1` meaning only the latest snapshot is pulled. That’s fine for search purposes. Not enough if you ever need blame or git history later.
