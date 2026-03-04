import logging
from typing import List, Dict, Optional
from cachetools import cached, TTLCache
from src.core.config import settings

logger = logging.getLogger(__name__)

# Simple cache for search results: 100 queries, expires in 1 hour
search_cache = TTLCache(maxsize=100, ttl=settings.CACHE_TTL)

class SearchService:
    def __init__(self):
        self.provider = settings.SEARCH_API_PROVIDER
        
    @cached(cache=search_cache)
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Execute search based on configured provider.
        Returns a list of dicts with 'title', 'href', 'body'.
        """
        logger.info(f"Searching internet for: '{query}' using {self.provider}")
        
        try:
            if self.provider == "duckduckgo":
                return self._search_duckduckgo(query, max_results)
            elif self.provider == "serpapi":
                return self._search_serpapi(query, max_results)
            elif self.provider == "bing":
                return self._search_bing(query, max_results)
            else:
                logger.warning(f"Unknown search provider: {self.provider}. Fallback to DuckDuckGo.")
                return self._search_duckduckgo(query, max_results)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, str]]:
        try:
            from duckduckgo_search import DDGS
            results = DDGS().text(query, max_results=max_results)
            # DDGS returns list of dicts: {'title':..., 'href':..., 'body':...}
            return results if results else []
        except ImportError:
            logger.error("duckduckgo-search not installed. Please install it.")
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    def _search_serpapi(self, query: str, max_results: int) -> List[Dict[str, str]]:
        if not settings.SERPAPI_API_KEY:
             logger.warning("SERPAPI_API_KEY not set. Returning empty results.")
             return []
        
        try:
            import requests
            params = {
                "engine": "google",
                "q": query,
                "api_key": settings.SERPAPI_API_KEY,
                "num": max_results
            }
            response = requests.get("https://serpapi.com/search", params=params)
            data = response.json()
            organic_results = data.get("organic_results", [])
            return [{"title": r.get("title"), "href": r.get("link"), "body": r.get("snippet")} for r in organic_results]
        except Exception as e:
            logger.error(f"SERP API error: {e}")
            return []

    def _search_bing(self, query: str, max_results: int) -> List[Dict[str, str]]:
        # TODO: Implement Bing Search API integration
        if not settings.BING_SEARCH_API_KEY:
             logger.warning("BING_SEARCH_API_KEY not set. Returning empty results.")
             return []
        # Mock implementation for now
        return []
