# tools/web_search.py
# ============================================================
# Web Search Tool — uses Tavily API.
# Called by execute_node when a step needs web_search.
# ============================================================

from config import cfg


def web_search(query: str) -> str:
    """
    Search the web using Tavily API.
    Returns formatted string of results.
    """
    if not cfg.TAVILY_API_KEY:
        return (
            "Web search unavailable — TAVILY_API_KEY not set in .env.\n"
            "Add your key from tavily.com to enable real web search."
        )

    try:
        from tavily import TavilyClient
        client  = TavilyClient(api_key=cfg.TAVILY_API_KEY)
        results = client.search(
            query=query,
            max_results=cfg.TAVILY_MAX_RESULTS,
            search_depth="basic",
        )

        if not results.get("results"):
            return f"No results found for: {query}"

        # Format results into clean readable text
        formatted = [f"Search results for: '{query}'\n"]
        for i, r in enumerate(results["results"], 1):
            formatted.append(
                f"{i}. {r.get('title', 'No title')}\n"
                f"   {r.get('content', '')[:300]}\n"
                f"   Source: {r.get('url', '')}"
            )

        return "\n".join(formatted)

    except Exception as e:
        return f"Web search error: {str(e)}"