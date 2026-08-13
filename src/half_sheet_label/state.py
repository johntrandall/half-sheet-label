"""Persistent 'which half is next' state, with pluggable backends.

Design note (2026-08-13): the top/bottom value is a property of the *physical
printer and the specific half-used sheet*, not of a user or a machine. We never
treat the stored value as ground truth — the CLI always shows the operator which
half it is about to print and lets them override. That makes any drift harmless
(worst case: you glance and correct).

Two backends:
  * local      — XDG_STATE_HOME JSON file, per user. Zero dependencies. Default.
  * cloudflare — a tiny Worker + Durable Object gives one shared, atomically
                 advanced counter across every family Mac, with NO NAS/mount
                 dependency. It DEGRADES GRACEFULLY: on any network error it
                 falls back to the local file and sets `.degraded = True` so the
                 CLI can warn. The network call is a convenience, never a hard
                 dependency.

Both backends expose the same interface: next_half / set_half / advance.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Protocol

HALVES = ("top", "bottom")


def _other(half: str) -> str:
    return "bottom" if half == "top" else "top"


def default_state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")
    return Path(base) / "half-sheet-label" / "state.json"


class StateBackend(Protocol):
    degraded: bool

    def next_half(self, printer: str) -> str: ...
    def set_half(self, printer: str, half: str) -> None: ...
    def advance(self, printer: str) -> str: ...


class LocalHalfState:
    """Tracks the next half per printer in a small JSON file."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_state_path()
        self.degraded = False

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {"printers": {}}

    def next_half(self, printer: str) -> str:
        entry = self._load().get("printers", {}).get(printer)
        if entry and entry.get("next_half") in HALVES:
            return entry["next_half"]
        return "top"  # a fresh sheet: top half first

    def set_half(self, printer: str, half: str) -> None:
        if half not in HALVES:
            raise ValueError(f"half must be one of {HALVES}, got {half!r}")
        data = self._load()
        data.setdefault("printers", {})[printer] = {
            "next_half": half,
            "updated": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2) + "\n")

    def advance(self, printer: str) -> str:
        nxt = _other(self.next_half(printer))
        self.set_half(printer, nxt)
        return nxt


class CloudflareHalfState:
    """Shared counter via a Cloudflare Worker + Durable Object.

    Falls back to a local file on any network/auth error so the tool keeps
    working offline. `degraded` reports whether the last operation hit the
    fallback path.
    """

    def __init__(self, base_url: str, token: str | None = None,
                 fallback: LocalHalfState | None = None, timeout: float = 4.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.fallback = fallback or LocalHalfState()
        self.timeout = timeout
        self.degraded = False

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("accept", "application/json")
        if data is not None:
            req.add_header("content-type", "application/json")
        if self.token:
            req.add_header("authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read() or b"{}")

    def next_half(self, printer: str) -> str:
        try:
            half = self._request("GET", f"/state/{printer}").get("next_half")
            self.degraded = False
            if half in HALVES:
                # keep the local mirror warm for offline fallback
                self.fallback.set_half(printer, half)
                return half
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
        self.degraded = True
        return self.fallback.next_half(printer)

    def set_half(self, printer: str, half: str) -> None:
        if half not in HALVES:
            raise ValueError(f"half must be one of {HALVES}, got {half!r}")
        self.fallback.set_half(printer, half)  # always mirror locally
        try:
            self._request("PUT", f"/state/{printer}", {"next_half": half})
            self.degraded = False
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            self.degraded = True

    def advance(self, printer: str) -> str:
        try:
            half = self._request("POST", f"/state/{printer}/advance").get("next_half")
            self.degraded = False
            if half in HALVES:
                self.fallback.set_half(printer, half)
                return half
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            pass
        self.degraded = True
        return self.fallback.advance(printer)


def get_backend(config: dict) -> StateBackend:
    """Build the configured state backend. `config` is the parsed config.toml."""
    state_cfg = config.get("state", {}) if config else {}
    local = LocalHalfState(state_cfg.get("path"))
    if state_cfg.get("backend") == "cloudflare":
        url = state_cfg.get("url")
        if not url:
            # misconfigured — fail safe to local rather than erroring a print
            return local
        return CloudflareHalfState(url, token=state_cfg.get("token"), fallback=local)
    return local
