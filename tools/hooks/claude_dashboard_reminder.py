#!/usr/bin/env python3
"""Claude Code PostToolUse hook: after a successful `git commit`, remind Claude to
refresh the progress dashboard (a git hook cannot upload to it; only Claude can).

Reads the hook payload on stdin; prints nothing unless the command was a commit.
Configured in .claude/settings.json.
"""
import json
import re
import sys

DASHBOARD = "https://claude.ai/artifact/HJouFMXmC3fZy2iSKUEBcX"

try:
    payload = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
command = str(payload.get("tool_input", {}).get("command", ""))
if not re.search(r"\bgit\b[^\n;&|]*\bcommit\b", command) or "--dry-run" in command:
    sys.exit(0)

print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": (
    "A git commit just landed in crisis-beat-decomp. The pre-commit hook refreshed "
    "out/progress/*.json and the README status block. Refresh the progress dashboard "
    f"{DASHBOARD}: upload each out/progress/*.json as an asset (Artifact publish, asset: true, "
    "one call per file), then update datasets/<name> with the new source.url and "
    "updated {at, by} (ArtifactData batch, pinned with if_version), and re-read "
    "data/users/me/check. Skip this only if the commit did not run the pre-commit hook "
    "(no disc, or CB_SKIP_PROGRESS)."
)}}))
