"""Per-IP sliding-window rate limiting for sensitive endpoints.

In-memory on purpose: the engine runs as a single uvicorn process on the
Mac Mini, so a process-local store is correct and avoids a Redis dependency.
Behind the Cloudflare Tunnel the client address is always the local
cloudflared process — the real IP arrives in ``CF-Connecting-IP``.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_WINDOWS: dict[str, deque] = defaultdict(deque)
_LOCK = threading.Lock()
_MAX_KEYS = 10_000  # hard cap so the store cannot grow unbounded


def reset() -> None:
    """Clear all windows (test isolation)."""
    with _LOCK:
        _WINDOWS.clear()


def client_ip(request: Request) -> str:
    return (
        request.headers.get("cf-connecting-ip")
        or (request.client.host if request.client else "unknown")
    )


def rate_limit(scope: str, max_calls: int, window_s: float):
    """Dependency factory: at most ``max_calls`` per ``window_s`` per IP."""

    async def _dep(request: Request) -> None:
        # Read at call time (mirrors data_root) so tests can monkeypatch it.
        if os.environ.get("ESCORA_RATE_LIMIT_DISABLED"):
            return
        key = f"{scope}:{client_ip(request)}"
        now = time.monotonic()
        with _LOCK:
            if len(_WINDOWS) > _MAX_KEYS:
                _WINDOWS.clear()
            window = _WINDOWS[key]
            while window and now - window[0] > window_s:
                window.popleft()
            if len(window) >= max_calls:
                raise HTTPException(
                    status_code=429,
                    detail="Muitas tentativas. Aguarde um minuto e tente novamente.",
                )
            window.append(now)

    return _dep
