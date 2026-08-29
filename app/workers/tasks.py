import os
import shutil
import tempfile

from git import Repo as GitRepo
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models import Repository, CodeChunk, RepoStatus
from app.services.parser import parse_repository
from app.services.embeddings import generate_embeddings_batch

EMBEDDING_BATCH_SIZE = 50


@celery_app.task(name="process_repository_task", bind=True)
def process_repository_task(self, repo_url: str, repo_id: str):
    db: Session = SessionLocal()
    temp_dir = tempfile.mkdtemp(prefix="repo_clone_")

    try:
        repo_record = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo_record:
            return {"status": "error", "message": "Repository record not found"}

        repo_record.status = RepoStatus.PROCESSING
        db.commit()

        # 1. Clone the repo
        GitRepo.clone_from(repo_url, temp_dir, depth=1)

        # 2. Parse it into chunks
        chunks = parse_repository(temp_dir)

        if not chunks:
            repo_record.status = RepoStatus.COMPLETED
            db.commit()
            return {"status": "completed", "chunks_ingested": 0}

        # 3. Generate embeddings in batches + bulk insert
        total_ingested = 0
        for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[i:i + EMBEDDING_BATCH_SIZE]
            texts = [c.content for c in batch]
            embeddings = generate_embeddings_batch(texts)

            db_objects = [
                CodeChunk(
                    repository_id=repo_record.id,
                    file_path=chunk.file_path,
                    symbol_name=chunk.symbol_name,
                    entity_type=chunk.entity_type,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    embedding=embedding,
                )
                for chunk, embedding in zip(batch, embeddings)
            ]
            db.bulk_save_objects(db_objects)
            db.commit()
            total_ingested += len(db_objects)

        # 4. Mark completed
        repo_record.status = RepoStatus.COMPLETED
        db.commit()

        return {"status": "completed", "chunks_ingested": total_ingested}

    except Exception as e:
        db.rollback()
        repo_record = db.query(Repository).filter(Repository.id == repo_id).first()
        if repo_record:
            repo_record.status = RepoStatus.FAILED
            repo_record.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()
        shutil.rmtree(temp_dir, ignore_errors=True)