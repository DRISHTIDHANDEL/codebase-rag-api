from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embeddings import generate_embedding

RRF_K = 60  # standard constant used in Reciprocal Rank Fusion


def hybrid_search(db: Session, repo_id: str, query_text: str, top_k: int = 5):
    query_embedding = generate_embedding(query_text)

    # --- 1. Dense vector search (cosine distance) ---
    vector_sql = text("""
        SELECT id, file_path, symbol_name, content, start_line, end_line,
               embedding <=> CAST(:query_embedding AS vector) AS distance
        FROM code_chunks
        WHERE repository_id = :repo_id
        ORDER BY distance ASC
        LIMIT :limit
    """)
    vector_results = db.execute(
        vector_sql,
        {"query_embedding": str(query_embedding), "repo_id": repo_id, "limit": top_k * 3},
    ).fetchall()

    # --- 2. Sparse keyword search (full-text) ---
    keyword_sql = text("""
        SELECT id, file_path, symbol_name, content, start_line, end_line,
               ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query_text)) AS rank
        FROM code_chunks
        WHERE repository_id = :repo_id
          AND to_tsvector('english', content) @@ plainto_tsquery('english', :query_text)
        ORDER BY rank DESC
        LIMIT :limit
    """)
    keyword_results = db.execute(
        keyword_sql,
        {"query_text": query_text, "repo_id": repo_id, "limit": top_k * 3},
    ).fetchall()

    # --- 3. Reciprocal Rank Fusion (RRF) ---
    scores = {}
    chunk_data = {}

    for rank, row in enumerate(vector_results, start=1):
        scores[row.id] = scores.get(row.id, 0) + 1 / (RRF_K + rank)
        chunk_data[row.id] = row

    for rank, row in enumerate(keyword_results, start=1):
        scores[row.id] = scores.get(row.id, 0) + 1 / (RRF_K + rank)
        chunk_data[row.id] = row

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)[:top_k]

    results = []
    for cid in ranked_ids:
        row = chunk_data[cid]
        results.append({
            "file_path": row.file_path,
            "symbol_name": row.symbol_name,
            "content": row.content,
            "start_line": row.start_line,
            "end_line": row.end_line,
        })

    return results