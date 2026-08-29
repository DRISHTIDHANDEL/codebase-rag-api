from typing import List
from sentence_transformers import SentenceTransformer

# Loads once when this module is first imported (slow first time, ~30-60s)
_model = SentenceTransformer("all-MiniLM-L6-v2")

EMBEDDING_DIM = 384  # this model outputs 384-dim vectors, NOT 1536


def generate_embedding(text: str) -> List[float]:
    """Generate a single embedding vector for a piece of text."""
    text = text.replace("\n", " ").strip()
    if not text:
        text = " "
    vector = _model.encode(text, convert_to_numpy=True)
    return vector.tolist()


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts in one batch call (fast, local, free)."""
    cleaned = [t.replace("\n", " ").strip() or " " for t in texts]
    vectors = _model.encode(cleaned, convert_to_numpy=True, batch_size=32)
    return [v.tolist() for v in vectors]