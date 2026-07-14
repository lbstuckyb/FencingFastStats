"""HTTP client for fie.org's Nuxt-rendered pages.

Every competition page embeds its data as a `<script id="__NUXT_DATA__">`
devalue-encoded JSON array (see `devalue.py`). This client fetches that
script's raw JSON, gzip-caches it to disk keyed by request path (so re-runs
of the decoder/parser never re-hit the network), and throttles real
requests to be polite to fie.org (checked `fie.org/robots.txt` on
2026-07-14: `User-Agent: *` / `Disallow:` — everything allowed).
"""
from __future__ import annotations

import gzip
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
BASE_URL = "https://fie.org"
NUXT_DATA_RE = re.compile(
    r'<script[^>]*\bid="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S
)
TOURNAMENT_URL_RE = re.compile(r"^/tournaments/(\d+)/(\d+)/event/(\d+)")

DEFAULT_CACHE_DIR = Path("data/raw_cache")


class FetchError(RuntimeError):
    pass


class FieClient:
    def __init__(
        self,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        throttle_seconds: float = 1.5,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.throttle_seconds = throttle_seconds
        self.timeout = timeout
        self._last_request_at: float = 0.0

        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.throttle_seconds - elapsed
        if wait > 0:
            time.sleep(wait)

    def _cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json.gz"

    def fetch_raw(self, path: str, cache_key: str, force: bool = False) -> dict:
        """Fetch a fie.org page and return `{"raw": <devalue JSON array>,
        "resolved_path": <path after redirects>}`. `raw` is still
        devalue-encoded — pass to `devalue.unflatten`.

        Cached to `{cache_dir}/{cache_key}.json.gz`; set `force=True` to
        bypass the cache and re-fetch.
        """
        cache_path = self._cache_path(cache_key)
        if not force and cache_path.exists():
            with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                return json.load(f)

        url = f"{BASE_URL}{path}"
        self._throttle()
        resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        self._last_request_at = time.monotonic()
        if resp.status_code != 200:
            raise FetchError(f"GET {url} -> HTTP {resp.status_code}")

        match = NUXT_DATA_RE.search(resp.text)
        if not match:
            raise FetchError(f"GET {url} -> no __NUXT_DATA__ script found")
        raw = json.loads(match.group(1))
        result = {"raw": raw, "resolved_path": urlparse(resp.url).path}

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with gzip.open(cache_path, "wt", encoding="utf-8") as f:
            json.dump(result, f)
        return result

    def fetch_competition(self, season: int, comp_id: int, force: bool = False) -> dict:
        """Fetch a competition page. Returns `{"raw", "resolved_path",
        "tournament_id"}` — `tournament_id` is parsed from the resolved
        `/tournaments/{season}/{tid}/event/{cid}/...` URL since the
        payload's own `tournamentId` field is often null.
        """
        result = self.fetch_raw(
            f"/competitions/{season}/{comp_id}",
            cache_key=f"competitions-{season}-{comp_id}",
            force=force,
        )
        tournament_id = comp_id
        m = TOURNAMENT_URL_RE.match(result["resolved_path"])
        if m:
            tournament_id = int(m.group(2))
        return {**result, "tournament_id": tournament_id}

    def fetch_results_ranking(
        self, season: int, comp_id: int, force: bool = False, page_size: int = 200
    ) -> list:
        """Fetch the full final-ranking list via the plain JSON API the site's
        client-side pagination calls (discovered by inspecting the site's JS
        bundles — not documented anywhere): `GET
        /api/fie/competition/{season}/{comp_id}/results/ranking?page=N&pageSize=M`.
        Unlike the SSR page (which always embeds page 1 of 24 server-side —
        later pages are client-side only), this endpoint honors `pageSize`
        directly, so one or two requests cover even large start lists.

        Cached whole (all pages already concatenated) to
        `{cache_dir}/results-ranking-{season}-{comp_id}.json.gz`.
        """
        cache_key = f"results-ranking-{season}-{comp_id}"
        cache_path = self._cache_path(cache_key)
        if not force and cache_path.exists():
            with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                return json.load(f)

        items: list = []
        page = 1
        while True:
            url = f"{BASE_URL}/api/fie/competition/{season}/{comp_id}/results/ranking"
            self._throttle()
            resp = self.session.get(
                url,
                params={"page": page, "pageSize": page_size},
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
            self._last_request_at = time.monotonic()
            if resp.status_code != 200:
                raise FetchError(f"GET {url} (page {page}) -> HTTP {resp.status_code}")
            data = resp.json()
            page_items = data.get("items", [])
            items.extend(page_items)
            total = data.get("totalFound", len(items))
            if not page_items or len(items) >= total:
                break
            page += 1

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with gzip.open(cache_path, "wt", encoding="utf-8") as f:
            json.dump(items, f)
        return items
