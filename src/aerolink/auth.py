"""Service-token authentication for the AeroControl integration (ADR-0003).

**This module is meant to be deleted.** It exists because `AGENTS.md` requires
authentication on every new API, while the real one (`AL-103`, Entra ID) is
blocked behind an open decision (`AL-R6`: Entra vs Django accounts). It
authenticates *one machine* on *one read-only endpoint* over loopback, which is
a question `AL-R6` does not answer either way.

The caducity clause lives in ADR-0003 and is the point of keeping this in its
own module with a single exported dependency: when `AL-103` lands it **replaces**
this rather than building on it. In particular this token must never gate a
write endpoint, never authenticate a person, and never grow a second token — a
second consumer is the signal to implement `AL-103`.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from aerolink.config import get_settings

logger = logging.getLogger("aerolink.auth")

_SCHEME = "token"


@dataclass(frozen=True)
class ServiceCaller:
    """Who is calling. Route code depends on this, not on "the token matched",
    so `AL-103` can return the same shape from a real identity without the
    routes changing."""

    subject: str
    workspace_slug: str


def _matches(candidate: str, configured: str) -> bool:
    """Constant-time comparison over digests.

    Hashing both sides first is one line more than comparing the raw values and
    buys two things: the comparison is always over equal-length inputs (no
    length oracle), and `compare_digest` cannot raise on a non-ASCII character
    pasted into the header.
    """
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode("utf-8")).digest(),
        hashlib.sha256(configured.encode("utf-8")).digest(),
    )


def require_service_token(request: Request) -> ServiceCaller:
    """Authenticate the integration caller, or refuse the request.

    Settings are read per request rather than captured from `create_app()`:
    `get_settings` is `lru_cache`d and the app is built at import time, so a
    closure would make the token impossible to configure in tests and
    impossible to rotate without an import-order dance.
    """
    settings = get_settings()

    # Fail closed. Not 401 -- that would send an operator off to rotate a token
    # that does not exist -- and above all not open. The consumer treats any
    # non-200 as an error and fails its scheduled job loudly, which is exactly
    # the behaviour a misconfigured gateway should produce.
    if not settings.service_token or not settings.service_token_workspace:
        logger.error("service_token_not_configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="integration credential not configured",
        )

    header = request.headers.get("Authorization", "")
    scheme, _, candidate = header.partition(" ")
    if scheme.casefold() != _SCHEME or not candidate:
        raise _unauthenticated(request, "missing or malformed credential")
    if not _matches(candidate, settings.service_token):
        raise _unauthenticated(request, "invalid credential")

    return ServiceCaller(
        subject=settings.service_token_subject,
        workspace_slug=settings.service_token_workspace,
    )


def _unauthenticated(request: Request, reason: str) -> HTTPException:
    # Logged, never audited: an audit row for an anonymous failure is nearly all
    # nulls, and writing one per failed attempt would hand an unauthenticated
    # caller an unbounded write into the audit table. Intrusion signal belongs
    # in the log, where rotation already bounds it.
    logger.warning(
        "service_token_rejected",
        extra={
            "reason": reason,
            "client": request.client.host if request.client else "unknown",
        },
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="unauthenticated",
        headers={"WWW-Authenticate": "Token"},
    )
