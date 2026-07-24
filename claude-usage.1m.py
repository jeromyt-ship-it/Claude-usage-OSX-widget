#!/usr/bin/env python3
# <xbar.title>Claude Usage</xbar.title>
# <xbar.version>v1.0</xbar.version>
# <xbar.author>Jeromy</xbar.author>
# <xbar.desc>Shows Claude Code session (5h) and weekly usage % in the menu bar.</xbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
#
# How it works: reads the Claude Code OAuth token from the macOS Keychain
# (read-only — never touches or refreshes it) and queries the same usage
# endpoint the `claude` CLI's `/usage` screen uses. Nothing leaves your
# machine except that one authenticated request to Anthropic's API.
#
# Setup: run `claude` (the CLI) and log in once, so the Keychain entry
# "Claude Code-credentials" exists. Then drop this file in your SwiftBar
# plugin folder and make it executable (chmod +x).
#
# The ".1m." in the filename tells SwiftBar to invoke this script every
# minute — but that does NOT mean it hits the network every minute. Each
# run first checks whether Claude/Claude Code looks active (a running
# `claude` or `Claude` process). If active, cached data older than
# ACTIVE_TTL is refreshed; if idle, we coast on cache for IDLE_TTL before
# bothering the API again. So: fast updates while you're working, quiet
# otherwise. You can also click "Refresh now" from the dropdown any time.

import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime

# A small hand-drawn starburst (9 tapered petals, Claude's brand orange
# #D97757), retina 44x44 canvas rendered at 22x22 via the pHYs 144dpi hint.
# Baked in once as a constant so the plugin has no image-generation cost at
# runtime and no dependency on SF Symbols availability.
ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACwAAAAsCAYAAAAehFoBAAAACXBIWXMAABYlAAAWJQFJUiTwAAAA"
    "2UlEQVR42u2ZUQ6AIAxDuaVH8ayeRn/9Iays20qAZD/GwOsgdczWdh/Pfb3/OMCRsPLQUsCWhSWA"
    "kcXLgXsAPQjJDDOBQ8QgWZ4VVwbtEZYG/F+MKSolywxB5dDlDjKCRoAlrM7yTMqfrVHySR5l2TIP"
    "TRwyCZrVkN1AJ2S8kwacEUtAp1tauXMwdkHq7iYHL31WZ8zda3tpGWXUzG5wJmw4NHrurCLCbh7e"
    "OgKpgUOBkYotvWj3dHtkm4MyN2QWsGRHcxngpRqEqANIHovzK0ERuqmPZUC3Hh8+HtGti0fG1AAA"
    "AABJRU5ErkJggg=="
)

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
KEYCHAIN_SERVICE = "Claude Code-credentials"
CACHE_FILE = os.path.expanduser("~/.cache/claude-usage-widget/cache.json")
ACTIVE_TTL = 60     # seconds — refresh cadence while a Claude session looks active
IDLE_TTL = 900       # seconds (15 min) — refresh cadence while idle


def get_token():
    """Return (token, error) from the macOS Keychain."""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return None, "keychain timeout"
    if out.returncode != 0:
        return None, "not logged in — run `claude` in Terminal once"
    try:
        creds = json.loads(out.stdout)["claudeAiOauth"]
    except (json.JSONDecodeError, KeyError):
        return None, "unexpected credential format"
    expires_at = creds.get("expiresAt")
    if expires_at and expires_at / 1000 < time.time():
        return None, "token expired — run `claude` once to refresh"
    return creds.get("accessToken"), None


def fetch_usage(token):
    """Return (usage dict, error)."""
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None, "token rejected — run `claude` once to refresh"
        if e.code == 429:
            return None, "rate-limited, try again shortly"
        return None, f"API error {e.code}"
    except Exception:
        return None, "offline?"


def is_claude_active():
    """True if a `claude` (CLI) or `Claude` (desktop app) process is running."""
    try:
        out = subprocess.run(["pgrep", "-i", "-x", "claude"], capture_output=True, timeout=5)
        return out.returncode == 0
    except Exception:
        return False  # fail closed: treat as idle, don't over-poll


def fetch_usage_cached(token, active):
    now = time.time()
    ttl = ACTIVE_TTL if active else IDLE_TTL
    cached = {}
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f)
    except Exception:
        pass

    if cached.get("usage") and now - cached.get("fetched_at", 0) < ttl:
        return cached["usage"], None

    usage, err = fetch_usage(token)
    if usage:
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump({"fetched_at": now, "usage": usage}, f)
        except Exception:
            pass
        return usage, None
    if cached.get("usage"):
        return cached["usage"], None  # stale data beats an error pill
    return None, err


# ANSI codes used for independently-colored spans within a single xbar/
# SwiftBar menu bar line (requires the `ansi=true` line attribute). Standard
# 16-color codes cover red/green; orange needs the extended 256-color form.
ANSI_RED = "\033[31m"
ANSI_ORANGE = "\033[38;5;208m"
ANSI_GREEN = "\033[32m"
ANSI_RESET = "\033[0m"


def color_word(pct):
    """Return 'red' / 'orange' / 'green' for a percentage, or None."""
    if pct is None:
        return None
    if pct >= 90:
        return "red"
    if pct >= 70:
        return "orange"
    return "green"


def color_for(pct):
    """Return ' | color=...' — ready to append to a dropdown line."""
    word = color_word(pct)
    return f" | color={word}" if word else ""


def ansi_wrap(text, pct):
    """Wrap text in ANSI color codes matching color_word(pct), for use on a
    single xbar line with ansi=true (so multiple percentages on the same
    line can each carry their own color)."""
    word = color_word(pct)
    if word is None:
        return text
    code = {"red": ANSI_RED, "orange": ANSI_ORANGE, "green": ANSI_GREEN}[word]
    return f"{code}{text}{ANSI_RESET}"


def reset_str(iso):
    try:
        local = datetime.fromisoformat(iso).astimezone()
        day = "today" if local.date() == datetime.now().astimezone().date() else local.strftime("%a")
        return f"resets {day} {local.strftime('%H:%M')}"
    except (ValueError, TypeError):
        return ""


def main():
    active = is_claude_active()
    token, err = get_token()
    usage = None
    if not err:
        usage, err = fetch_usage_cached(token, active)

    if err or not usage:
        print(f"⚠ | image={ICON_B64} color=orange")
        print("---")
        print(err or "unknown error")
        print("Refresh now | refresh=true")
        return

    five = usage.get("five_hour") or {}
    week = usage.get("seven_day") or {}
    s_pct = five.get("utilization")
    w_pct = week.get("utilization")

    # Session and weekly are colored independently (via ansi=true + per-span
    # ANSI codes) so a high weekly % doesn't tint a low session % red too —
    # each number's color reflects only its own percentage.
    if s_pct is not None and w_pct is not None:
        title = f"{ansi_wrap(f'{s_pct:.0f}', s_pct)}/{ansi_wrap(f'{w_pct:.0f}', w_pct)}%"
    elif s_pct is not None or w_pct is not None:
        pct = s_pct if s_pct is not None else w_pct
        title = ansi_wrap(f"{pct:.0f}%", pct)
    else:
        title = "?"
    # The starburst icon (ICON_B64) always stays brand-orange.
    print(f"{title} | image={ICON_B64} ansi=true")

    print("---")
    if s_pct is not None:
        print(f"Session (5h): {s_pct:.0f}%  {reset_str(five.get('resets_at'))}{color_for(s_pct)}")
    if w_pct is not None:
        print(f"Weekly: {w_pct:.0f}%  {reset_str(week.get('resets_at'))}{color_for(w_pct)}")

    extra = usage.get("extra_usage") or {}
    used_credits = extra.get("used_credits")
    monthly_limit = extra.get("monthly_limit")
    if extra.get("is_enabled") and used_credits is not None and monthly_limit:
        print(f"Extra usage: {used_credits / 100:.2f} / {monthly_limit / 100:.0f} {extra.get('currency', '')}")

    print("---")
    mode = "active — checking every 1m" if active else "idle — checking every 15m"
    print(f"Claude {mode} | font=Menlo size=11")
    print("Refresh now | refresh=true")


if __name__ == "__main__":
    main()
