"""Minimal HTTP client; all API operations are selected by server tools."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx


class CatMapperAPIError(Exception):
    """A CatMapper API request failed."""


class CatMapperClient:
    def __init__(self, base_url: str, api_key: str, transport=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ("https", "http") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/")):
            raise ValueError("CATMAPPER_API_URL must be an HTTPS origin without credentials, query, or fragment")
        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("CATMAPPER_API_URL must use HTTPS except on localhost")
        if not api_key or not api_key.strip():
            raise ValueError("Set CATMAPPER_API_KEY in the MCP client's secret configuration")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.transport = transport

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("CATMAPPER_API_URL", "https://api.catmapper.org"),
                   os.environ.get("CATMAPPER_API_KEY", ""))

    async def request(self, method: str, path: str, *, params=None, json=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Invalid API path")
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=120.0,
                                         follow_redirects=False, trust_env=False) as client:
                response = await client.request(method, self.base_url + path, params=params,
                                                json=json, headers={"X-API-Key": self.api_key})
        except httpx.RequestError as exc:
            raise CatMapperAPIError(f"CatMapper request failed: {type(exc).__name__}") from None
        if not response.is_success:
            message = response.text[:4000].replace(self.api_key, "[redacted]")
            raise CatMapperAPIError(f"CatMapper API returned HTTP {response.status_code}: {message}")
        try:
            return response.json()
        except ValueError:
            return response.text.replace(self.api_key, "[redacted]")
