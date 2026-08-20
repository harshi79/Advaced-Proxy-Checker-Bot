from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Optional
from urllib.parse import quote


SUPPORTED_SCHEMES = ("http", "https", "socks4", "socks5")


@dataclass(frozen=True, slots=True)
class ProxyCandidate:
    host: str
    port: int
    scheme: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    source_line: str = field(default="", repr=False, compare=False)

    def identity(self) -> tuple[str, int, str, str, str]:
        return (
            self.host.lower(),
            self.port,
            self.scheme or "auto",
            self.username or "",
            self.password or "",
        )

    def with_scheme(self, scheme: str) -> "ProxyCandidate":
        return ProxyCandidate(
            host=self.host,
            port=self.port,
            scheme=scheme,
            username=self.username,
            password=self.password,
            source_line=self.source_line,
        )

    def url(self, scheme: Optional[str] = None) -> str:
        selected = (scheme or self.scheme or "http").lower()
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        auth = ""
        if self.username is not None:
            auth = quote(self.username, safe="")
            if self.password is not None:
                auth += f":{quote(self.password, safe='')}"
            auth += "@"
        return f"{selected}://{auth}{host}:{self.port}"

    def display(self, scheme: Optional[str] = None) -> str:
        return self.url(scheme or self.scheme or "http")


@dataclass(slots=True)
class ParseResult:
    received_lines: int
    valid_entries: list[ProxyCandidate]
    invalid_lines: int
    duplicate_lines: int


@dataclass(slots=True)
class ProxyCheckResult:
    proxy: ProxyCandidate
    working: bool
    checked_scheme: Optional[str] = None
    latency_ms: Optional[float] = None
    exit_ip: Optional[str] = None
    anonymity: str = "unknown"
    status_code: Optional[int] = None
    error: Optional[str] = None


@dataclass(slots=True)
class JobStats:
    received_lines: int
    valid_entries: int
    invalid_lines: int
    duplicate_lines: int
    checked: int = 0
    working: int = 0
    started_at: float = field(default_factory=monotonic)
    finished_at: Optional[float] = None

    @property
    def remaining(self) -> int:
        return max(self.valid_entries - self.checked, 0)

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or monotonic()
        return max(end - self.started_at, 0.0)

    @property
    def failed(self) -> int:
        return max(self.checked - self.working, 0)
