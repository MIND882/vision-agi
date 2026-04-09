# tools/db_query.py
# ============================================================
# DB QUERY TOOL — Internal knowledge base lookup.
#
# Tries in order:
#   1. ChromaDB semantic search (episodic memory)
#   2. PostgreSQL fact lookup (semantic memory)
#   3. Returns "no data" — never crashes the pipeline
#
# Why this exists:
#   The decompose node sometimes plans a db_query step
#   to check "internal knowledge". This tool handles it
#   gracefully instead of "Unknown tool — skipping".
# ============================================================

from config import cfg


def db_query(query: str) -> str:
    """
    Query internal knowledge base.
    Tries ChromaDB first, then PostgreSQL, then returns empty.

    Args:
        query: Natural language question or keyword to search

    Returns:
        String with found knowledge, or "No internal data found"
    """
    results = []

    # ── 1. ChromaDB — episodic memory search ─────────────────
    chroma_result = _search_chromadb(query)
    if chroma_result:
        results.append(f"[Episodic Memory]\n{chroma_result}")

    # ── 2. PostgreSQL — semantic facts search ─────────────────
    postgres_result = _search_postgres(query)
    if postgres_result:
        results.append(f"[Semantic Facts]\n{postgres_result}")

    # ── 3. Return combined or empty ───────────────────────────
    if results:
        return "\n\n".join(results)

    return f"[DB] No internal knowledge found for: '{query}'"


def _search_chromadb(query: str) -> str:
    """Search episodic memory (ChromaDB) for relevant past experiences."""
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        client = chromadb.PersistentClient(path=cfg.CHROMA_PERSIST_DIR)
        ef     = embedding_functions.DefaultEmbeddingFunction()

        # Try episodes collection first
        try:
            collection = client.get_collection(
                name="episodes",
                embedding_function=ef
            )
        except Exception:
            return ""

        results = collection.query(
            query_texts=[query],
            n_results=3,
            include=["documents", "metadatas", "distances"]
        )

        docs      = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return ""

        # Only return results with decent similarity (distance < 1.5)
        relevant = []
        for doc, meta, dist in zip(docs, metadatas, distances):
            if dist < 1.5:
                score   = meta.get("score", 0)
                outcome = meta.get("outcome", "")
                relevant.append(
                    f"• [{outcome} | quality={score:.2f}] {doc[:200]}"
                )

        return "\n".join(relevant) if relevant else ""

    except ImportError:
        return ""
    except Exception as e:
        print(f"  [DB_QUERY] ChromaDB search failed: {e}")
        return ""


def _search_postgres(query: str) -> str:
    """Search semantic facts table in PostgreSQL."""
    try:
        import psycopg2

        conn = psycopg2.connect(cfg.POSTGRES_DSN)
        cur  = conn.cursor()

        # Simple keyword search in facts table
        # Uses ILIKE for case-insensitive partial match
        search_term = f"%{query[:100]}%"

        cur.execute("""
            SELECT fact_text, confidence, created_at
            FROM semantic_facts
            WHERE fact_text ILIKE %s
            ORDER BY confidence DESC, created_at DESC
            LIMIT 5
        """, (search_term,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            return ""

        facts = []
        for row in rows:
            fact_text, confidence, created_at = row
            facts.append(
                f"• [confidence={confidence:.2f}] {fact_text[:200]}"
            )

        return "\n".join(facts)

    except ImportError:
        return ""
    except Exception as e:
        # DB might not have semantic_facts table yet — that's fine
        if "does not exist" in str(e).lower():
            return ""
        print(f"  [DB_QUERY] PostgreSQL search failed: {e}")
        return ""


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing db_query tool...")
    print()

    test_queries = [
        "India IT sector",
        "Python AI applications",
        "capital of France",
    ]

    for q in test_queries:
        print(f"Query: '{q}'")
        result = db_query(q)
        print(f"Result: {result[:200]}")
        print("-" * 40)