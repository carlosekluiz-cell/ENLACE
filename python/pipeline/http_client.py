"""Shared HTTP client for all data pipelines.

Provides retry with exponential backoff, streaming downloads with resume,
CKAN dataset URL resolution, and paginated GeoJSON fetching.
"""
import csv
import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd

from python.pipeline.config import PIPELINE_DEFAULTS

logger = logging.getLogger(__name__)

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
DOWNLOAD_CACHE_DIR = Path(os.getenv("DOWNLOAD_CACHE_DIR", "/tmp/enlace_cache"))


class PipelineHTTPClient:
    """HTTP client with retry, streaming, and CKAN support."""

    def __init__(
        self,
        max_retries: int = PIPELINE_DEFAULTS["max_retries"],
        timeout: int = PIPELINE_DEFAULTS["download_timeout_seconds"],
        base_delay: float = 2.0,
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_delay = base_delay
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=30.0),
            follow_redirects=True,
            headers={"User-Agent": "ENLACE-Pipeline/1.0"},
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _retry_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with retry and exponential backoff."""
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.request(method, url, **kwargs)
                if resp.status_code in RETRY_STATUS_CODES and attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        delay = max(delay, int(retry_after))
                    logger.warning(
                        f"HTTP {resp.status_code} from {url}, retry {attempt+1}/{self.max_retries} in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                last_exc = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Connection error for {url}: {e}, retry {attempt+1}/{self.max_retries} in {delay:.1f}s"
                    )
                    time.sleep(delay)
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    def get_json(self, url: str, params: Optional[dict] = None) -> Any:
        """GET request returning parsed JSON."""
        resp = self._retry_request("GET", url, params=params)
        return resp.json()

    def get_csv(
        self,
        url: str,
        sep: str = ",",
        encoding: str = "utf-8",
        params: Optional[dict] = None,
    ) -> pd.DataFrame:
        """Download a CSV file and return as DataFrame."""
        resp = self._retry_request("GET", url, params=params)
        content = resp.content.decode(encoding, errors="replace")
        return pd.read_csv(io.StringIO(content), sep=sep, dtype=str, on_bad_lines="skip")

    def download_file(
        self,
        url: str,
        dest: Path,
        resume: bool = True,
    ) -> Path:
        """Download a file with optional resume support. Returns path to file."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)

        headers = {}
        mode = "wb"
        if resume and dest.exists():
            existing_size = dest.stat().st_size
            headers["Range"] = f"bytes={existing_size}-"
            mode = "ab"
            logger.info(f"Resuming download from byte {existing_size}")

        with self._client.stream("GET", url, headers=headers, follow_redirects=True) as resp:
            if resp.status_code == 416:  # Range not satisfiable = already complete
                logger.info(f"File already fully downloaded: {dest}")
                return dest
            if resp.status_code == 200 and mode == "ab":
                # Server doesn't support range; restart
                mode = "wb"
            resp.raise_for_status()

            total = resp.headers.get("Content-Length")
            downloaded = 0
            with open(dest, mode) as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)

            logger.info(f"Downloaded {downloaded:,} bytes to {dest}")

        return dest

    def resolve_ckan_resource_url(
        self,
        dataset_id: str,
        resource_format: str = "CSV",
        ckan_base: str = "https://dados.gov.br/dados/api/3/action",
    ) -> str:
        """Resolve a CKAN dataset ID to the actual resource download URL.

        CKAN's package_show returns metadata including a list of resources.
        We find the first resource matching the desired format and return its URL.
        """
        resp = self.get_json(f"{ckan_base}/package_show", params={"id": dataset_id})
        result = resp.get("result", resp) if isinstance(resp, dict) else resp

        resources = result.get("resources", [])
        if not resources:
            raise ValueError(f"No resources found for CKAN dataset '{dataset_id}'")

        # Find resource matching format
        for resource in resources:
            fmt = (resource.get("format") or "").upper()
            if fmt == resource_format.upper():
                url = resource.get("url", "")
                if url:
                    logger.info(f"Resolved CKAN '{dataset_id}' -> {url}")
                    return url

        # Fallback: return the first resource with a URL
        for resource in resources:
            url = resource.get("url", "")
            if url:
                logger.warning(
                    f"No {resource_format} resource for '{dataset_id}', using first available: {url}"
                )
                return url

        raise ValueError(f"No downloadable resource found for CKAN dataset '{dataset_id}'")

    def get_paginated_geojson(
        self,
        base_url: str,
        page_size: int = 1000,
        max_features: Optional[int] = None,
        where: str = "1=1",
        out_fields: str = "*",
    ) -> list[dict]:
        """Fetch paginated GeoJSON from an ArcGIS REST API.

        ArcGIS Feature Services return results in pages via resultOffset/resultRecordCount.
        We paginate until we get an empty result or exceededTransferLimit is False.
        """
        all_features = []
        offset = 0

        while True:
            params = {
                "where": where,
                "outFields": out_fields,
                "f": "geojson",
                "resultRecordCount": page_size,
                "resultOffset": offset,
            }
            data = self.get_json(base_url, params=params)

            features = data.get("features", [])
            if not features:
                break

            all_features.extend(features)
            offset += len(features)

            if max_features and len(all_features) >= max_features:
                all_features = all_features[:max_features]
                break

            exceeded = data.get("properties", {}).get("exceededTransferLimit", True)
            if not exceeded:
                break

            logger.info(f"Fetched {len(all_features)} features so far (offset={offset})")

        logger.info(f"Total features fetched: {len(all_features)}")
        return all_features


def get_cache_path(filename: str) -> Path:
    """Get path to a cached file, creating cache directory if needed."""
    DOWNLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOAD_CACHE_DIR / filename
