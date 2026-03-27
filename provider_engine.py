#!/usr/bin/env python3
"""
provider_engine.py — Multi-provider AI router with auto-failover
Handles all 21 provider APIs, response normalization, and seamless switching.
"""

import os, json, time, urllib.request, urllib.error
from typing import Optional, Generator

# ── Response normalization ─────────────────────────────────────
def extract_text(provider_type: str, data: dict) -> Optional[str]:
    """Normalize response from any provider into plain text."""
    try:
        if provider_type in ("openai_compat", "cloudflare"):
            return data["choices"][0]["message"]["content"]
        elif provider_type == "gemini":
            return data["candidates"][0]["content"]["parts"][0]["text"]
        elif provider_type == "anthropic":
            return data["content"][0]["text"]
        elif provider_type == "ollama":
            # Ollama /api/chat
            if "message" in data:
                return data["message"]["content"]
            # Ollama /api/generate (legacy)
            return data.get("response", "")
        elif provider_type == "huggingface":
            if isinstance(data, list):
                return data[0].get("generated_text", "")
            return data.get("generated_text", "")
    except (KeyError, IndexError, TypeError):
        pass
    return None


# ── Build request for each provider type ──────────────────────
def build_request(provider: dict, messages: list, model: str, stream: bool = False) -> dict:
    """Return (url, headers, body) for a given provider."""
    ptype = provider["type"]
    api_key = os.environ.get(provider["env_key"], "") if provider.get("env_key") else ""
    
    if ptype == "openai_compat":
        url = provider["base_url"].rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if "extra_headers" in provider:
            headers.update(provider["extra_headers"])
        body = {"model": model, "messages": messages, "stream": stream}
        return url, headers, body

    elif ptype == "gemini":
        # Convert OpenAI-style messages to Gemini format
        contents = []
        system_text = ""
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            elif m["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": m["content"]}]})
        
        url = f"{provider['base_url']}/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        body = {"contents": contents}
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}
        return url, headers, body

    elif ptype == "anthropic":
        url = provider["base_url"].rstrip("/") + "/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        # Separate system from messages
        system = ""
        msgs = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                msgs.append(m)
        body = {"model": model, "max_tokens": 4096, "messages": msgs}
        if system:
            body["system"] = system
        return url, headers, body

    elif ptype == "cloudflare":
        account_id = os.environ.get(provider["account_env"], "")
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # CF uses OpenAI-like format
        body = {"messages": messages}
        return url, headers, body

    elif ptype == "ollama":
        base = (
            os.environ.get(provider.get("base_url_env", ""), "") or
            provider.get("default_base_url", "http://localhost:11434")
        )
        url = base.rstrip("/") + "/api/chat"
        headers = {"Content-Type": "application/json"}
        if provider.get("env_key") and os.environ.get(provider["env_key"]):
            headers["Authorization"] = f"Bearer {os.environ[provider['env_key']]}"
        body = {"model": model, "messages": messages, "stream": False}
        return url, headers, body

    elif ptype == "huggingface":
        endpoint = os.environ.get("HUGGINGFACE_ENDPOINT_URL", "")
        if not endpoint:
            endpoint = f"https://api-inference.huggingface.co/models/{model}"
        url = endpoint
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # HF expects a flat prompt
        prompt = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        ) + "\nASSISTANT:"
        body = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 2048, "return_full_text": False},
        }
        return url, headers, body

    raise ValueError(f"Unknown provider type: {ptype}")


# ── HTTP call ──────────────────────────────────────────────────
def http_post(url: str, headers: dict, body: dict, timeout: int = 45) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


# ── Core call with error capture ──────────────────────────────
def call_provider(provider: dict, messages: list, model: str) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (text, error_msg).
    On success: (text, None). On failure: (None, error_msg).
    """
    try:
        url, headers, body = build_request(provider, messages, model)
        data = http_post(url, headers, body)
        text = extract_text(provider["type"], data)
        if text is None:
            return None, f"Unparseable response: {json.dumps(data)[:200]}"
        return text, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return None, f"HTTP {e.code}: {body}"
    except urllib.error.URLError as e:
        return None, f"Network: {e.reason}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


# ── Failover router ────────────────────────────────────────────
class ProviderRouter:
    def __init__(self, providers: list, verbose: bool = True):
        self.providers = providers
        self.verbose = verbose
        self._current_idx = 0
        self._failed: set = set()

    def _available(self) -> list:
        """Providers with keys configured, not permanently failed."""
        result = []
        for p in self.providers:
            pid = p["id"]
            if pid in self._failed:
                continue
            # Check if key exists (skip keyless providers if no base URL)
            env_key = p.get("env_key")
            if env_key:
                if not os.environ.get(env_key, "").strip():
                    continue  # No key set
            elif p["type"] == "ollama":
                pass  # Ollama needs no key
            else:
                continue
            result.append(p)
        return result

    def get_model(self, provider: dict) -> str:
        env = provider.get("env_model")
        if env:
            return os.environ.get(env, provider["default_model"])
        return provider["default_model"]

    def chat(self, messages: list) -> tuple[str, str]:
        """
        Attempts providers in order with failover.
        Returns (response_text, provider_id_used).
        Raises RuntimeError if all fail.
        """
        candidates = self._available()
        if not candidates:
            raise RuntimeError("No providers configured. Set at least one API key.")

        for provider in candidates:
            model = self.get_model(provider)
            if self.verbose:
                _spinner_start(f"  {provider['name']}  [{model}]")
            
            text, err = call_provider(provider, messages, model)
            _spinner_stop()

            if text is not None:
                return text, provider["id"]
            else:
                if self.verbose:
                    _print_failover(provider["id"], err)
                # Don't permanently blacklist — could be rate limit
                # But skip for this session if hard error
                if err and ("401" in err or "403" in err or "invalid" in err.lower()):
                    self._failed.add(provider["id"])

        raise RuntimeError(
            "All configured providers failed. Check your API keys and network."
        )

    def status(self) -> list:
        """Return list of (provider_id, has_key, is_failed)."""
        rows = []
        for p in self.providers:
            env_key = p.get("env_key")
            has_key = bool(env_key and os.environ.get(env_key, "").strip()) or p["type"] == "ollama"
            rows.append({
                "id": p["id"],
                "name": p["name"],
                "has_key": has_key,
                "failed": p["id"] in self._failed,
            })
        return rows


# ── Spinner (non-blocking) ─────────────────────────────────────
import threading, sys

_spinner_active = False
_spinner_thread = None
_spinner_msg = ""

def _spinner_start(msg: str):
    global _spinner_active, _spinner_thread, _spinner_msg
    _spinner_active = True
    _spinner_msg = msg
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def _run():
        i = 0
        while _spinner_active:
            sys.stdout.write(f"\r\033[36m{frames[i % len(frames)]}\033[0m {_spinner_msg}   ")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
    _spinner_thread = threading.Thread(target=_run, daemon=True)
    _spinner_thread.start()

def _spinner_stop():
    global _spinner_active
    _spinner_active = False
    if _spinner_thread:
        _spinner_thread.join(timeout=0.5)
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

def _print_failover(pid: str, err: str):
    print(f"\033[33m  ⚡ {pid} failed → trying next provider\033[0m")
    if err:
        print(f"\033[2m    {err[:100]}\033[0m")
