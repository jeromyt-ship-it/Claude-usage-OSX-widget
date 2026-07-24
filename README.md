# Claude Usage Widget

A tiny SwiftBar plugin that shows your Claude session (5h) and weekly usage % in the macOS menu bar.

![menu bar example](https://img.shields.io/badge/menu%20bar-29%2F88%25-D97757)

## Requirements

- macOS
- [SwiftBar](https://github.com/swiftbar/SwiftBar) (`brew install swiftbar`)
- Python 3 (preinstalled on macOS)
- The [`claude`](https://claude.com/product/claude-code) CLI, logged in at least once

## Setup

1. Install SwiftBar if you haven't already:
   ```
   brew install swiftbar
   ```
2. Log in with the Claude Code CLI once, so your credentials exist in the macOS Keychain:
   ```
   claude
   ```
3. Clone or download this repo, and make the script executable:
   ```
   chmod +x claude-usage.1m.py
   ```
4. Open SwiftBar. On first launch it asks you to pick a **Plugin Folder** — point it at (or move `claude-usage.1m.py` into) that folder.
5. Refresh SwiftBar (menu bar icon → Refresh All Plugins). You should see something like `29/88%` appear.

Click the menu bar item for a full breakdown (session %, weekly %, reset times).

## How it works

The script reads your Claude Code OAuth token from the macOS Keychain (**read-only** — it never modifies or refreshes it) and calls the same internal endpoint the `claude` CLI's `/usage` screen uses. Nothing is sent anywhere except that one authenticated request to Anthropic's own API — no third-party service, no cookies.

That endpoint (`api.anthropic.com/api/oauth/usage`) is undocumented and internal to Claude Code, so a future CLI update could change its shape and break this script. If that happens, open an issue.

## Refresh behavior

SwiftBar runs the script every minute, but it only calls the API if a `claude`/`Claude` process looks active and the cached data is over 60 seconds old. While idle, it serves cached data and only refetches every 15 minutes. Adjust `ACTIVE_TTL` / `IDLE_TTL` at the top of the script to change this.

## License

MIT — do whatever you want with it.
