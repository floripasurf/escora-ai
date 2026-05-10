"""Small in-process rate limiter for auth endpoints."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import DefaultDict, Deque

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitConfig:
    limit: int
    window_seconds: int


_lock = threading.Lock()
_attempts: DefaultDict[str, Deque[float]] = defaultdict(deque)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def config_for(action: str) -> RateLimitConfig:
    prefix = f"ESCORA_{action.upper()}_RATE_LIMIT"
    return RateLimitConfig(
        limit=max(1, _env_int(f"{prefix}_MAX", 20 if action == "login" else 10)),
        window_seconds=max(1, _env_int(f"{prefix}_WINDOW_SECONDS", 60)),
    )


def client_key(request: Request, action: str, identifier: str) -> str:
    host = request.client.host if request.client else "unknown"
    normalized = identifier.strip().lower()
    return f"{action}:{host}:{normalized}"


def check_rate_limit(request: Request, *, action: str, identifier: str) -> None:
    cfg = config_for(action)
    now = time.time()
    cutoff = now - cfg.window_seconds
    key = client_key(request, action, identifier)

    with _lock:
        attempts = _attempts[key]
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        if len(attempts) >= cfg.limit:
            logger.warning(
                "auth_rate_limited",
                extra={
                    "action": action,
                    "identifier": identifier.strip().lower(),
                    "limit": cfg.limit,
                    "window_seconds": cfg.window_seconds,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde alguns instantes e tente novamente.",
            )
        attempts.append(now)


def log_auth_event(action: str, identifier: str, outcome: str) -> None:
    logger.info(
        "auth_event",
        extra={
            "action": action,
            "identifier": identifier.strip().lower(),
            "outcome": outcome,
        },
    )


def _reset_for_tests() -> None:
    with _lock:
        _attempts.clear()
