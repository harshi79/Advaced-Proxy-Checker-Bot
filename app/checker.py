from __future__ import annotations

import asyncio
import json
import logging
import re
from time import perf_counter
from typing import Any, Optional

import aiohttp
from aiohttp_socks import ProxyConnector

from .config import Settings
from .models import ProxyCandidate, ProxyCheckResult

LOGGER = logging.getLogger(__name__)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[0-9a-fA-F:]{3,39}\b")


class ProxyChecker:
    """Check HTTP(S), SOCKS4, and SOCKS5 candidates without logging secrets."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._timeout = aiohttp.ClientTimeout(
            total=settings.check_timeout_seconds,
            connect=settings.check_timeout_seconds,
            sock_connect=settings.check_timeout_seconds,
            sock_read=settings.check_timeout_seconds,
        )
        self._headers = {
            "User-Agent": "advanced-proxy-checker/1.0",
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.1",
            "Cache-Control": "no-cache",
        }

    async def check(self, candidate: ProxyCandidate) -> ProxyCheckResult:
        schemes = [candidate.scheme] if candidate.scheme else ["http", "socks5", "socks4"]
        tasks = [asyncio.create_task(self._check_with_retries(candidate, scheme)) for scheme in schemes]
        results: list[ProxyCheckResult] = []
        try:
            for task in asyncio.as_completed(tasks):
                result = await task
                results.append(result)
                if result.working:
                    for other in tasks:
                        if not other.done():
                            other.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return result
            return self._best_failure(results, candidate)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_with_retries(self, candidate: ProxyCandidate, scheme: str) -> ProxyCheckResult:
        last: Optional[ProxyCheckResult] = None
        attempts = self.settings.check_retries + 1
        for attempt in range(attempts):
            last = await self._check_once(candidate, scheme)
            if last.working or attempt + 1 >= attempts:
                return last
            await asyncio.sleep(min(0.15 * (attempt + 1), 0.5))
        assert last is not None
        return last

    async def _check_once(self, candidate: ProxyCandidate, scheme: str) -> ProxyCheckResult:
        started = perf_counter()
        try:
            if scheme in {"socks4", "socks5"}:
                result = await self._check_socks(candidate, scheme)
            else:
                result = await self._check_http(candidate, scheme)
            result.latency_ms = round((perf_counter() - started) * 1000, 2)
            return result
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the bot reports a safe short reason
            elapsed = round((perf_counter() - started) * 1000, 2)
            return ProxyCheckResult(
                proxy=candidate,
                working=False,
                checked_scheme=scheme,
                latency_ms=elapsed,
                error=self._safe_error(exc),
            )

    async def _check_http(self, candidate: ProxyCandidate, scheme: str) -> ProxyCheckResult:
        # aiohttp has broad HTTP proxy support. An https:// proxy URL is tried
        # first for explicit HTTPS entries; some aiohttp versions only support
        # HTTP CONNECT, so a transparent fallback is attempted once.
        proxy_url = candidate.url(scheme)
        try:
            return await self._request_through_http(candidate, scheme, proxy_url)
        except Exception:
            if scheme != "https":
                raise
            return await self._request_through_http(candidate, scheme, candidate.url("http"))

    async def _request_through_http(
        self,
        candidate: ProxyCandidate,
        scheme: str,
        proxy_url: str,
    ) -> ProxyCheckResult:
        connector = aiohttp.TCPConnector(limit=1, ssl=True, enable_cleanup_closed=True)
        async with aiohttp.ClientSession(
            timeout=self._timeout,
            connector=connector,
            headers=self._headers,
            trust_env=False,
        ) as session:
            async with session.get(
                self.settings.check_url,
                proxy=proxy_url,
                allow_redirects=False,
            ) as response:
                body = await response.content.read(1_000_000)
                if response.status >= 400:
                    return ProxyCheckResult(
                        proxy=candidate,
                        working=False,
                        checked_scheme=scheme,
                        status_code=response.status,
                        error=f"target returned {response.status}",
                    )
                exit_ip = _extract_ip(body, response.headers.get("content-type", ""))
                anonymity = "unknown"
                if self.settings.header_echo_url:
                    anonymity = await self._probe_headers(session)
                return ProxyCheckResult(
                    proxy=candidate,
                    working=True,
                    checked_scheme=scheme,
                    exit_ip=exit_ip,
                    anonymity=anonymity,
                    status_code=response.status,
                )

    async def _check_socks(self, candidate: ProxyCandidate, scheme: str) -> ProxyCheckResult:
        connector = ProxyConnector.from_url(candidate.url(scheme), rdns=scheme == "socks5")
        async with aiohttp.ClientSession(
            timeout=self._timeout,
            connector=connector,
            headers=self._headers,
            trust_env=False,
        ) as session:
            async with session.get(self.settings.check_url, allow_redirects=False) as response:
                body = await response.content.read(1_000_000)
                if response.status >= 400:
                    return ProxyCheckResult(
                        proxy=candidate,
                        working=False,
                        checked_scheme=scheme,
                        status_code=response.status,
                        error=f"target returned {response.status}",
                    )
                exit_ip = _extract_ip(body, response.headers.get("content-type", ""))
                anonymity = "unknown"
                if self.settings.header_echo_url:
                    anonymity = await self._probe_headers(session)
                return ProxyCheckResult(
                    proxy=candidate,
                    working=True,
                    checked_scheme=scheme,
                    exit_ip=exit_ip,
                    anonymity=anonymity,
                    status_code=response.status,
                )

    async def _probe_headers(self, session: aiohttp.ClientSession) -> str:
        try:
            async with session.get(
                self.settings.header_echo_url,
                allow_redirects=False,
            ) as response:
                payload = await response.content.read(1_000_000)
                if response.status >= 400:
                    return "unknown"
                try:
                    data: Any = json.loads(payload.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    data = {}
                headers = data.get("headers", data) if isinstance(data, dict) else {}
                lowered = {str(key).lower(): str(value) for key, value in headers.items()}
                forwarded = any(
                    key in lowered and lowered[key].strip()
                    for key in ("forwarded", "via", "x-forwarded-for", "x-real-ip", "client-ip")
                )
                return "transparent" if forwarded else "anonymous"
        except Exception:  # noqa: BLE001 - optional metadata must not fail a check
            return "unknown"

    @staticmethod
    def _best_failure(results: list[ProxyCheckResult], candidate: ProxyCandidate) -> ProxyCheckResult:
        if not results:
            return ProxyCheckResult(proxy=candidate, working=False, error="no protocol response")
        # Prefer the most informative failure and avoid exposing a URL or auth.
        return max(results, key=lambda result: result.latency_ms or 0)

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        name = exc.__class__.__name__.lower()
        if isinstance(exc, asyncio.TimeoutError) or "timeout" in name:
            return "timeout"
        if isinstance(exc, aiohttp.InvalidURL):
            return "invalid proxy url"
        if isinstance(exc, (ConnectionError, OSError)):
            return "connection failed"
        text = str(exc).lower()
        if "ssl" in text or "certificate" in text:
            return "tls error"
        if "authentication" in text or "auth" in text:
            return "authentication failed"
        return name.replace("error", "failure")[:48] or "check failed"


def _extract_ip(body: bytes, content_type: str) -> Optional[str]:
    text = body.decode("utf-8", errors="replace").strip()
    if "json" in content_type.lower():
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                for key in ("ip", "origin", "address"):
                    value = payload.get(key)
                    if value:
                        return str(value).split(",", 1)[0].strip()
        except json.JSONDecodeError:
            pass
    match = _IP_RE.search(text)
    return match.group(0) if match else None
