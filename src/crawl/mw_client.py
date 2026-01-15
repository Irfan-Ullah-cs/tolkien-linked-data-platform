from __future__ import annotations

import time
import random
from typing import Any, Dict, Optional

import requests
import requests_cache

from configs.settings import TG_API, USER_AGENT, HTTP_CACHE_PATH

# Cache all HTTP GETs for 30 days. Makes re-runs fast and avoids hammering the wiki.
requests_cache.install_cache(HTTP_CACHE_PATH, backend="sqlite", expire_after=60 * 60 * 24 * 30)


class MediaWikiClient:
    def __init__(
        self,
        api_url: str = TG_API,
        user_agent: str = USER_AGENT,
        min_delay: float = 0.4,
        max_delay: float = 1.0,
    ):
        self.api_url = api_url
        self.session = requests.Session()

        self.session.headers.update({"User-Agent": user_agent})
        self.min_delay = min_delay
        self.max_delay = max_delay

    def _sleep_polite(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def get_json(self, params: Dict[str, Any], retries: int = 5, timeout: int = 30) -> Dict[str, Any]:
        params = dict(params)
        params.setdefault("format", "json")
        params.setdefault("formatversion", "2")

        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                self._sleep_polite()
                r = self.session.get(self.api_url, params=params, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_exc = e
                time.sleep(min(8, 0.7 * attempt))

        raise RuntimeError(f"MediaWiki API request failed after {retries} retries: {params}") from last_exc
