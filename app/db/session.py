from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# The engine manages the actual connection pool to Postgres
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # checks connection is alive before using it (avoids stale connection errors)
    echo=settings.DEBUG,  # logs SQL queries to console when DEBUG=True — helpful while learning
)

# SessionLocal is a factory — every request/task will call this to get its own DB session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency — gives each request a fresh DB session,
    and guarantees it closes even if an error happens.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()