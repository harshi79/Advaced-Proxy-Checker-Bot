from __future__ import annotations

import re
from typing import Optional
from urllib.parse import unquote, urlsplit

from .models import ParseResult, ProxyCandidate, SUPPORTED_SCHEMES

_SUPPORTED = set(SUPPORTED_SCHEMES)
_SCHEME_ALIASES = {"socks5h": "socks5", "socks": "socks5"}


def _clean_line(line: str) -> str:
    line = line.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", ";", "//")):
        return ""
    # Keep passwords containing # intact when they are part of a URL. For
    # ordinary list lines, a whitespace-prefixed # is an inline comment.
    line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
    return line.strip("<>\"'")


def _normalise_scheme(scheme: Optional[str]) -> Optional[str]:
    if not scheme:
        return None
    scheme = scheme.lower().rstrip(":")
    return _SCHEME_ALIASES.get(scheme, scheme)


def _valid_host(host: str) -> bool:
    if not host or any(char.isspace() for char in host):
        return False
    if any(char in host for char in "/\\@"):
        return False
    return len(host) <= 255


def _port(value: str) -> Optional[int]:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _candidate(
    host: str,
    port: str,
    scheme: Optional[str],
    username: Optional[str],
    password: Optional[str],
    source_line: str,
) -> Optional[ProxyCandidate]:
    host = host.strip().strip("[]")
    scheme = _normalise_scheme(scheme)
    parsed_port = _port(port)
    if scheme not in (*_SUPPORTED, None) or not _valid_host(host) or parsed_port is None:
        return None
    if username == "":
        username = None
    if password == "":
        password = None
    return ProxyCandidate(
        host=host,
        port=parsed_port,
        scheme=scheme,
        username=unquote(username) if username is not None else None,
        password=unquote(password) if password is not None else None,
        source_line=source_line,
    )


def _from_url(line: str) -> Optional[ProxyCandidate]:
    try:
        parsed = urlsplit(line)
        scheme = _normalise_scheme(parsed.scheme)
        if scheme not in _SUPPORTED or not parsed.hostname or parsed.port is None:
            return None
        return _candidate(
            parsed.hostname,
            str(parsed.port),
            scheme,
            parsed.username,
            parsed.password,
            line,
        )
    except ValueError:
        return None


def _from_host_port(line: str) -> Optional[ProxyCandidate]:
    # user:password@host:port
    auth: Optional[str] = None
    endpoint = line
    if "@" in line:
        auth, endpoint = line.rsplit("@", 1)

    username: Optional[str] = None
    password: Optional[str] = None
    if auth is not None:
        if ":" in auth:
            username, password = auth.split(":", 1)
        else:
            username = auth

    endpoint = endpoint.strip()
    host: Optional[str] = None
    port: Optional[str] = None

    # [IPv6]:port and [IPv6]|port
    bracketed = re.match(r"^\[([^\]]+)\]\s*(?::|[|,;\s])\s*(\d+)$", endpoint)
    if bracketed:
        host, port = bracketed.group(1), bracketed.group(2)
    else:
        # host:port, host|port, host,port, and host port
        match = re.match(r"^([^\s|,;:]+)\s*(?::|[|,;\s])\s*(\d+)$", endpoint)
        if match:
            host, port = match.group(1), match.group(2)

    if host is not None and port is not None:
        return _candidate(host, port, None, username, password, line)

    # Common host:port:user:password format. It is intentionally handled
    # after the normal forms so an IPv6 address cannot be misread silently.
    parts = line.split(":")
    if len(parts) == 4 and parts[1].isdigit():
        return _candidate(parts[0], parts[1], None, parts[2], parts[3], line)
    return None


def parse_proxy_line(line: str) -> Optional[ProxyCandidate]:
    cleaned = _clean_line(line)
    if not cleaned:
        return None
    if "://" in cleaned:
        return _from_url(cleaned)
    return _from_host_port(cleaned)


def parse_proxy_text(text: str) -> ParseResult:
    received = 0
    invalid = 0
    duplicates = 0
    entries: list[ProxyCandidate] = []
    seen: set[tuple[str, int, str, str, str]] = set()

    for raw_line in text.splitlines():
        if _clean_line(raw_line):
            received += 1
        candidate = parse_proxy_line(raw_line)
        if candidate is None:
            if _clean_line(raw_line):
                invalid += 1
            continue
        identity = candidate.identity()
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        entries.append(candidate)

    return ParseResult(
        received_lines=received,
        valid_entries=entries,
        invalid_lines=invalid,
        duplicate_lines=duplicates,
    )


def decode_text(data: bytes) -> str:
    if not data:
        return ""
    # NUL-heavy content is almost certainly not a text proxy list.
    if data.count(b"\x00") >= max(4, len(data) // 100):
        raise ValueError("the file does not look like a text file")
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("the file encoding is not supported")
