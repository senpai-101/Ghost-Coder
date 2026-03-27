#!/usr/bin/env python3
"""
session.py — Conversation session management for GHOST
Handles context window, history persistence, token estimation, and cost tracking.
"""

import os, json, time, hashlib
from pathlib import Path
from typing import Optional

SESSIONS_DIR = Path.home() / ".ghost" / "sessions"
CONTEXT_CONFIG = {
    "max_messages": 50,       # Rolling window
    "max_chars": 60_000,      # Approximate context limit
    "summary_threshold": 40,  # Messages before compressing old turns
}


class Session:
    def __init__(self, session_id: Optional[str] = None, workspace: str = "."):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or _new_id()
        self.workspace = str(Path(workspace).resolve())
        self.messages: list = []
        self.metadata = {
            "created": time.time(),
            "last_active": time.time(),
            "provider_used": [],
            "turns": 0,
            "workspace": self.workspace,
        }
        self._path = SESSIONS_DIR / f"{self.session_id}.json"
        
        # Load existing if found
        if self._path.exists():
            self._load()

    # ── Message management ─────────────────────────────────────
    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})
        self._trim_context()

    def add_assistant(self, content: str, provider_id: str = ""):
        self.messages.append({"role": "assistant", "content": content})
        self.metadata["turns"] += 1
        self.metadata["last_active"] = time.time()
        if provider_id and provider_id not in self.metadata["provider_used"]:
            self.metadata["provider_used"].append(provider_id)

    def add_tool_result(self, result: str):
        """Inject tool result as a user-side message."""
        self.messages.append({
            "role": "user",
            "content": f"[TOOL RESULT]\n{result}",
        })

    def get_messages(self, system_prompt: str = "") -> list:
        """Return full message list for API call."""
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(self.messages)
        return msgs

    def _trim_context(self):
        """Keep context within limits by removing oldest messages."""
        # Count total chars
        total = sum(len(m["content"]) for m in self.messages)
        
        # Remove oldest pairs (user+assistant) when over limit
        while (total > CONTEXT_CONFIG["max_chars"] or 
               len(self.messages) > CONTEXT_CONFIG["max_messages"]) and len(self.messages) > 2:
            removed = self.messages.pop(0)
            total -= len(removed["content"])

    # ── Persistence ────────────────────────────────────────────
    def save(self):
        data = {
            "session_id": self.session_id,
            "messages": self.messages,
            "metadata": self.metadata,
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self):
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self.messages = data.get("messages", [])
            self.metadata.update(data.get("metadata", {}))
        except Exception:
            pass

    def clear(self):
        self.messages = []
        self.metadata["turns"] = 0

    # ── Stats ──────────────────────────────────────────────────
    def stats(self) -> dict:
        total_chars = sum(len(m["content"]) for m in self.messages)
        est_tokens = total_chars // 4
        return {
            "session_id": self.session_id,
            "turns": self.metadata["turns"],
            "messages_in_context": len(self.messages),
            "estimated_tokens": est_tokens,
            "providers_used": self.metadata["provider_used"],
            "workspace": self.workspace,
        }


# ── Session list ───────────────────────────────────────────────
def list_sessions() -> list:
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for p in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text())
            meta = data.get("metadata", {})
            sessions.append({
                "id": data.get("session_id", p.stem),
                "turns": meta.get("turns", 0),
                "last_active": meta.get("last_active", 0),
                "workspace": meta.get("workspace", ""),
            })
        except Exception:
            continue
    return sessions[:20]  # Return 20 most recent


def _new_id() -> str:
    return hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]
