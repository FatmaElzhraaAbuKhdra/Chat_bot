"""
learning/embeddings.py — Vector Embeddings for Semantic Search
Gemini text-embedding-004 for Arabic-aware embeddings.
Stores vectors in Oracle BLOB / SQLite JSON.
"""
import os
import json
import struct
import hashlib
import logging
import math
from typing import Optional
from .store import get_conn, tbl, is_oracle

log = logging.getLogger("learning.embeddings")

_EMBED_MODEL = "text-embedding-004"
_EMBED_DIM = 768

_T = lambda: tbl("embeddings_cache")


# ═══════════════════════════════════════════════════════════════════
# Embedding Generation
# ═══════════════════════════════════════════════════════════════════

def _get_embedding_gemini(text: str) -> list[float] | None:
    """Generate embedding using Gemini API."""
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model=f"models/{_EMBED_MODEL}",
            content=text,
            task_type="SEMANTIC_SIMILARITY",
        )
        return result["embedding"]
    except Exception as e:
        log.debug(f"[EMBEDDING] Gemini embedding failed: {e}")
        return None


def _embed_to_bytes(embedding: list[float]) -> bytes:
    """Pack float list into bytes for Oracle BLOB storage."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def _bytes_to_embed(data: bytes) -> list[float]:
    """Unpack bytes back to float list."""
    n = len(data) // 4
    return list(struct.unpack(f'{n}f', data))


def get_embedding(text: str, category: str = "question") -> list[float] | None:
    """Get embedding — checks cache first, then generates via API."""
    text_hash = hashlib.md5(text.encode()).hexdigest()

    # Check cache
    with get_conn() as conn:
        if is_oracle():
            row = conn.execute(f"""
                SELECT EMBEDDING_BLOB FROM {_T()}
                WHERE TEXT_HASH = :1
            """, (text_hash,)).fetchone()
            if row:
                blob = row.get("embedding_blob") or row.get("EMBEDDING_BLOB")
                if blob:
                    return _bytes_to_embed(blob.read() if hasattr(blob, 'read') else blob)
        else:
            row = conn.execute(f"""
                SELECT embedding_json FROM {_T()}
                WHERE text_hash = ?
            """, (text_hash,)).fetchone()
            if row:
                return json.loads(row["embedding_json"])

    # Generate
    embedding = _get_embedding_gemini(text)
    if embedding is None:
        return None

    # Cache
    with get_conn() as conn:
        if is_oracle():
            # Check if exists first, then insert or update
            exists = conn.execute(f"""
                SELECT 1 FROM {_T()} WHERE TEXT_HASH = :1
            """, (text_hash,)).fetchone()
            if exists:
                conn.execute(f"""
                    UPDATE {_T()} SET EMBEDDING_BLOB = :1
                    WHERE TEXT_HASH = :2
                """, (_embed_to_bytes(embedding), text_hash))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (TEXT_CONTENT, TEXT_HASH, EMBEDDING_BLOB, CATEGORY)
                    VALUES (:1, :2, :3, :4)
                """, (text, text_hash, _embed_to_bytes(embedding), category))
        else:
            conn.execute(f"""
                INSERT OR REPLACE INTO {_T()}
                    (text_content, text_hash, embedding_json, category)
                VALUES (?, ?, ?, ?)
            """, (text, text_hash, json.dumps(embedding), category))

    return embedding


# ═══════════════════════════════════════════════════════════════════
# Similarity Search
# ═══════════════════════════════════════════════════════════════════

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar(
    query: str,
    category: str = "",
    top_k: int = 5,
    min_score: float = 0.7,
) -> list[dict]:
    """Find semantically similar texts in the embeddings cache."""
    query_emb = get_embedding(query, "query")
    if query_emb is None:
        return []

    with get_conn() as conn:
        if is_oracle():
            if category:
                rows = conn.execute(f"""
                    SELECT TEXT_CONTENT, EMBEDDING_BLOB, CATEGORY, METADATA_JSON
                    FROM {_T()} WHERE CATEGORY = :1
                """, (category,)).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT TEXT_CONTENT, EMBEDDING_BLOB, CATEGORY, METADATA_JSON
                    FROM {_T()}
                """).fetchall()
        else:
            if category:
                rows = conn.execute(f"""
                    SELECT text_content, embedding_json, category, metadata_json
                    FROM {_T()} WHERE category = ?
                """, (category,)).fetchall()
            else:
                rows = conn.execute(f"""
                    SELECT text_content, embedding_json, category, metadata_json
                    FROM {_T()}
                """).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        # Get embedding
        if is_oracle():
            blob = d.get("embedding_blob") or d.get("EMBEDDING_BLOB")
            if not blob:
                continue
            stored_emb = _bytes_to_embed(blob.read() if hasattr(blob, 'read') else blob)
        else:
            emb_json = d.get("embedding_json")
            if not emb_json:
                continue
            stored_emb = json.loads(emb_json)

        score = cosine_similarity(query_emb, stored_emb)
        if score >= min_score:
            meta_raw = d.get("metadata_json") or d.get("METADATA_JSON") or "{}"
            try:
                meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}

            text = d.get("text_content") or d.get("TEXT_CONTENT", "")
            cat = d.get("category") or d.get("CATEGORY", "")

            results.append({
                "text": text,
                "category": cat,
                "score": round(score, 4),
                "metadata": meta,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def find_similar_intent(question: str, top_k: int = 3) -> list[dict]:
    """Find similar past questions and their intents."""
    return find_similar(question, category="question", top_k=top_k, min_score=0.75)


# ═══════════════════════════════════════════════════════════════════
# Index Building
# ═══════════════════════════════════════════════════════════════════

def index_question(question: str, sub_intent: str, domain: str = "",
                   template: str = "") -> bool:
    """Add a question to the embedding index."""
    metadata = {
        "sub_intent": sub_intent,
        "domain": domain,
        "template": template,
    }
    embedding = get_embedding(question, "question")
    if embedding is None:
        return False

    text_hash = hashlib.md5(question.encode()).hexdigest()
    meta_json = json.dumps(metadata)

    with get_conn() as conn:
        if is_oracle():
            exists = conn.execute(f"""
                SELECT 1 FROM {_T()} WHERE TEXT_HASH = :1
            """, (text_hash,)).fetchone()
            if exists:
                conn.execute(f"""
                    UPDATE {_T()}
                    SET EMBEDDING_BLOB = :1, CATEGORY = 'question',
                        METADATA_JSON = :2
                    WHERE TEXT_HASH = :3
                """, (_embed_to_bytes(embedding), meta_json, text_hash))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (TEXT_CONTENT, TEXT_HASH, EMBEDDING_BLOB,
                         CATEGORY, METADATA_JSON)
                    VALUES (:1, :2, :3, 'question', :4)
                """, (question, text_hash, _embed_to_bytes(embedding), meta_json))
        else:
            conn.execute(f"""
                INSERT OR REPLACE INTO {_T()}
                    (text_content, text_hash, embedding_json,
                     category, metadata_json)
                VALUES (?, ?, ?, 'question', ?)
            """, (question, text_hash, json.dumps(embedding), meta_json))
    return True


def index_erp_term(term_ar: str, term_en: str, domain: str = "",
                   sub_intent: str = "") -> bool:
    """Add an ERP term to the embedding index."""
    text = f"{term_ar} — {term_en}"
    metadata = {"term_ar": term_ar, "term_en": term_en,
                "domain": domain, "sub_intent": sub_intent}
    embedding = get_embedding(text, "term")
    if embedding is None:
        return False

    text_hash = hashlib.md5(text.encode()).hexdigest()
    meta_json = json.dumps(metadata)

    with get_conn() as conn:
        if is_oracle():
            exists = conn.execute(f"""
                SELECT 1 FROM {_T()} WHERE TEXT_HASH = :1
            """, (text_hash,)).fetchone()
            if exists:
                conn.execute(f"""
                    UPDATE {_T()}
                    SET EMBEDDING_BLOB = :1, CATEGORY = 'term',
                        METADATA_JSON = :2
                    WHERE TEXT_HASH = :3
                """, (_embed_to_bytes(embedding), meta_json, text_hash))
            else:
                conn.execute(f"""
                    INSERT INTO {_T()}
                        (TEXT_CONTENT, TEXT_HASH, EMBEDDING_BLOB,
                         CATEGORY, METADATA_JSON)
                    VALUES (:1, :2, :3, 'term', :4)
                """, (text, text_hash, _embed_to_bytes(embedding), meta_json))
        else:
            conn.execute(f"""
                INSERT OR REPLACE INTO {_T()}
                    (text_content, text_hash, embedding_json,
                     category, metadata_json)
                VALUES (?, ?, ?, 'term', ?)
            """, (text, text_hash, json.dumps(embedding), meta_json))
    return True


# ═══════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════

def get_embedding_stats() -> dict:
    """Get embedding cache statistics."""
    with get_conn() as conn:
        row = conn.execute(f"""
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT category) AS categories,
                   SUM(CASE WHEN category='question' THEN 1 ELSE 0 END) AS questions,
                   SUM(CASE WHEN category='term' THEN 1 ELSE 0 END) AS terms,
                   SUM(CASE WHEN category='concept' THEN 1 ELSE 0 END) AS concepts
            FROM {_T()}
        """).fetchone()
        return dict(row) if row else {}
