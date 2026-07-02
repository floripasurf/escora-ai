#!/usr/bin/env python3
"""Verify the currently configured estrutura.app runtime target."""

from __future__ import annotations

import argparse
import json
import plistlib
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
VERCEL_JSON = REPO / "vercel.json"
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.escora.engine.plist"
CLOUDFLARED_CONFIG = Path.home() / ".cloudflared/config.escora.yml"
ACTIVE_REPO = Path.home() / "escora-ai"
MAC_TUNNEL_HOST = "https://escora.blackcube.dev"


def load_vercel_destination() -> str:
    data = json.loads(VERCEL_JSON.read_text())
    rewrites = data.get("rewrites", [])
    for rewrite in rewrites:
        if rewrite.get("source") == "/api/:path*":
            return rewrite.get("destination", "")
    return ""


def load_launch_agent() -> dict:
    if not LAUNCH_AGENT.exists():
        return {}
    with LAUNCH_AGENT.open("rb") as fh:
        return plistlib.load(fh)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-current-mac-tunnel",
        action="store_true",
        help="Accept the current Mac Mini + Cloudflare tunnel production target.",
    )
    args = parser.parse_args()

    destination = load_vercel_destination()
    launch_agent = load_launch_agent()
    cloudflared = CLOUDFLARED_CONFIG.read_text() if CLOUDFLARED_CONFIG.exists() else ""
    program_args = launch_agent.get("ProgramArguments", [])

    checks = {
        "repo": str(REPO),
        "active_repo_expected": str(ACTIVE_REPO),
        "vercel_api_destination": destination,
        "launch_agent_exists": LAUNCH_AGENT.exists(),
        "launch_agent_uses_active_repo": any(str(ACTIVE_REPO) in arg for arg in program_args),
        "cloudflared_config_exists": CLOUDFLARED_CONFIG.exists(),
        "cloudflared_routes_to_local_8020": "localhost:8020" in cloudflared,
        "mac_tunnel_dependency": destination.startswith(MAC_TUNNEL_HOST),
    }
    print(json.dumps(checks, indent=2, ensure_ascii=False))

    hard_failures = [
        key for key in (
            "launch_agent_exists",
            "launch_agent_uses_active_repo",
            "cloudflared_config_exists",
            "cloudflared_routes_to_local_8020",
        )
        if not checks[key]
    ]
    if hard_failures:
        print(f"Runtime check failed: {', '.join(hard_failures)}", file=sys.stderr)
        return 1

    if checks["mac_tunnel_dependency"] and not args.allow_current_mac_tunnel:
        print(
            "Runtime check failed: Vercel API traffic still depends on the Mac Mini tunnel.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
