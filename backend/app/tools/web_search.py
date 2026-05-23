"""Web search tool — DuckDuckGo, no API key needed."""
from duckduckgo_search import DDGS


def web_search_tool(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo and return list of {title, url, snippet}."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        return [{"title": "Search error", "url": "", "snippet": str(e)}]
