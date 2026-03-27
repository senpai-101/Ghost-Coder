#!/usr/bin/env python3
"""
GHOST — Generative Heuristic Orchestration Shell Terminal
A free, provider-agnostic Claude Code clone for Termux.
Auto-failover across 21 AI providers. Zero Anthropic dependency.

Usage:
    python ghost.py                    # Interactive REPL
    python ghost.py "your prompt"      # One-shot query
    python ghost.py --workspace /path  # Set workspace
    python ghost.py --status           # Show provider status
"""

import os, sys, argparse
from pathlib import Path

# ── Provider registry (priority order: fastest/most generous free tiers first) ─
PROVIDERS = [
    {
        "id": "GROQ",
        "name": "Groq (LLaMA 3.3-70B)",
        "env_key": "GROQ_API_KEY",
        "env_model": "GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
        "type": "openai_compat",
        "base_url": "https://api.groq.com/openai/v1",
    },
    {
        "id": "CEREBRAS",
        "name": "Cerebras (LLaMA 3.3-70B)",
        "env_key": "CEREBRAS_API_KEY",
        "env_model": "CEREBRAS_MODEL",
        "default_model": "llama3.3-70b",
        "type": "openai_compat",
        "base_url": "https://api.cerebras.ai/v1",
    },
    {
        "id": "GEMINI",
        "name": "Google Gemini 2.0 Flash",
        "env_key": "GEMINI_API_KEY",
        "env_model": "GEMINI_MODEL",
        "default_model": "gemini-2.0-flash",
        "type": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
    },
    {
        "id": "OPENROUTER",
        "name": "OpenRouter (DeepSeek R1 Free)",
        "env_key": "OPENROUTER_API_KEY",
        "env_model": "OPENROUTER_MODEL",
        "default_model": "deepseek/deepseek-r1:free",
        "type": "openai_compat",
        "base_url": "https://openrouter.ai/api/v1",
        "extra_headers": {
            "HTTP-Referer": "http://localhost:7777",
            "X-Title": "GHOST",
        },
    },
    {
        "id": "MISTRAL",
        "name": "Mistral Small",
        "env_key": "MISTRAL_API_KEY",
        "env_model": "MISTRAL_MODEL",
        "default_model": "mistral-small-latest",
        "type": "openai_compat",
        "base_url": "https://api.mistral.ai/v1",
    },
    {
        "id": "TOGETHER",
        "name": "Together AI (LLaMA 3.3-70B)",
        "env_key": "TOGETHER_API_KEY",
        "env_model": "TOGETHER_MODEL",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "type": "openai_compat",
        "base_url": "https://api.together.xyz/v1",
    },
    {
        "id": "COHERE",
        "name": "Cohere Command-R",
        "env_key": "COHERE_API_KEY",
        "env_model": "COHERE_MODEL",
        "default_model": "command-r7b-12-2024",
        "type": "openai_compat",
        "base_url": "https://api.cohere.ai/compatibility/v1",
    },
    {
        "id": "HYPERBOLIC",
        "name": "Hyperbolic (LLaMA 3.3-70B)",
        "env_key": "HYPERBOLIC_API_KEY",
        "env_model": "HYPERBOLIC_MODEL",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "type": "openai_compat",
        "base_url": "https://api.hyperbolic.xyz/v1",
    },
    {
        "id": "NVIDIA",
        "name": "NVIDIA NIM (LLaMA 3.3-70B)",
        "env_key": "NVIDIA_API_KEY",
        "env_model": "NVIDIA_MODEL",
        "default_model": "meta/llama-3.3-70b-instruct",
        "type": "openai_compat",
        "base_url": "https://integrate.api.nvidia.com/v1",
    },
    {
        "id": "GITHUB",
        "name": "GitHub Models (GPT-4o-mini)",
        "env_key": "GITHUB_TOKEN",
        "env_model": "GITHUB_MODEL",
        "default_model": "gpt-4o-mini",
        "type": "openai_compat",
        "base_url": "https://models.inference.ai.azure.com",
    },
    {
        "id": "XAI",
        "name": "xAI Grok-3 Mini",
        "env_key": "XAI_API_KEY",
        "env_model": "XAI_MODEL",
        "default_model": "grok-3-mini",
        "type": "openai_compat",
        "base_url": "https://api.x.ai/v1",
    },
    {
        "id": "CLOUDFLARE",
        "name": "Cloudflare Workers AI",
        "env_key": "CLOUDFLARE_API_TOKEN",
        "env_model": "CLOUDFLARE_MODEL",
        "default_model": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "type": "cloudflare",
        "account_env": "CLOUDFLARE_ACCOUNT_ID",
    },
    {
        "id": "VENICE",
        "name": "Venice AI (LLaMA 3.3-70B)",
        "env_key": "VENICE_API_KEY",
        "env_model": "VENICE_MODEL",
        "default_model": "llama-3.3-70b",
        "type": "openai_compat",
        "base_url": "https://api.venice.ai/api/v1",
    },
    {
        "id": "MOONSHOT",
        "name": "Moonshot AI (Kimi)",
        "env_key": "MOONSHOT_API_KEY",
        "env_model": "MOONSHOT_MODEL",
        "default_model": "moonshot-v1-32k",
        "type": "openai_compat",
        "base_url": "https://api.moonshot.ai/v1",
    },
    {
        "id": "ZAI",
        "name": "Z.AI GLM-4 Flash",
        "env_key": "ZAI_API_KEY",
        "env_model": "ZAI_MODEL",
        "default_model": "glm-4-flash",
        "type": "openai_compat",
        "base_url": "https://api.z.ai/api/paas/v4",
    },
    {
        "id": "LONGCAT",
        "name": "LongCat Flash",
        "env_key": "LONGCAT_API_KEY",
        "env_model": "LONGCAT_MODEL",
        "default_model": "LongCat-Flash-Chat",
        "type": "openai_compat",
        "base_url": "https://api.longcat.chat/openai/native",
    },
    {
        "id": "OPENAI",
        "name": "OpenAI (GPT-4o-mini)",
        "env_key": "OPENAI_API_KEY",
        "env_model": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
        "type": "openai_compat",
        "base_url": "https://api.openai.com/v1",
    },
    {
        "id": "ANTHROPIC",
        "name": "Anthropic Claude",
        "env_key": "ANTHROPIC_API_KEY",
        "env_model": "ANTHROPIC_MODEL",
        "default_model": "claude-haiku-4-5-20251001",
        "type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
    },
    {
        "id": "HUGGINGFACE",
        "name": "Hugging Face Inference",
        "env_key": "HUGGINGFACE_TOKEN",
        "env_model": "HUGGINGFACE_MODEL",
        "default_model": "microsoft/Phi-3.5-mini-instruct",
        "type": "huggingface",
    },
    {
        "id": "OLLAMA",
        "name": "Ollama (Local)",
        "env_key": None,
        "env_model": "OLLAMA_MODEL",
        "default_model": "llama3.2",
        "type": "ollama",
        "base_url_env": "OLLAMA_BASE_URL",
        "default_base_url": "http://localhost:11434",
    },
    {
        "id": "OLLAMA_CLOUD",
        "name": "Ollama Cloud",
        "env_key": "OLLAMA_CLOUD_API_KEY",
        "env_model": "OLLAMA_CLOUD_MODEL",
        "default_model": "llama3.2",
        "type": "ollama",
        "base_url_env": "OLLAMA_CLOUD_BASE_URL",
    },
]


def main():
    parser = argparse.ArgumentParser(
        description="GHOST — Free multi-provider Claude Code clone for Termux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ghost                                # Interactive REPL
  ghost "write a fibonacci function"   # One-shot query
  ghost --workspace ~/myproject        # Set workspace directory
  ghost --provider GEMINI              # Force specific provider
  ghost --model GROQ mixtral-8x7b-32768  # Override model
  ghost --status                       # Show all provider status
  ghost --no-tools "explain async/await"  # Chat only, no tools
  ghost --list-providers               # List all provider IDs
        """
    )
    parser.add_argument("prompt", nargs="?", help="One-shot prompt (skips interactive REPL)")
    parser.add_argument("--workspace", "-w", default=".", help="Working directory (default: .)")
    parser.add_argument("--provider", "-p", help="Force specific provider ID (e.g. GEMINI)")
    parser.add_argument("--model", "-m", nargs=2, metavar=("PROVIDER", "MODEL"),
                        help="Override model: --model GROQ mixtral-8x7b-32768")
    parser.add_argument("--status", "-s", action="store_true", help="Show provider status and exit")
    parser.add_argument("--no-tools", action="store_true", help="Disable agentic tool use (chat only)")
    parser.add_argument("--list-providers", "-l", action="store_true", help="List all provider IDs")
    args = parser.parse_args()

    # Set workspace
    workspace = str(Path(args.workspace).resolve())
    if not Path(workspace).exists():
        print(f"Error: workspace '{workspace}' not found")
        sys.exit(1)
    os.chdir(workspace)

    # Apply model override
    if args.model:
        pid, model_name = args.model
        pid = pid.upper()
        for p in PROVIDERS:
            if p["id"] == pid:
                env_key = p.get("env_model")
                if env_key:
                    os.environ[env_key] = model_name
                break

    # Reorder providers if --provider set
    providers = PROVIDERS.copy()
    if args.provider:
        pid = args.provider.upper()
        matched = [p for p in providers if p["id"] == pid]
        if not matched:
            print(f"Unknown provider: {pid}")
            print(f"Valid IDs: {', '.join(p['id'] for p in PROVIDERS)}")
            sys.exit(1)
        others = [p for p in providers if p["id"] != pid]
        providers = matched + others

    # List providers
    if args.list_providers:
        print("\n  GHOST Provider IDs:\n")
        for p in PROVIDERS:
            env_key = p.get("env_key")
            has_key = (env_key and os.environ.get(env_key, "").strip()) or p["type"] == "ollama"
            icon = "✓" if has_key else "·"
            print(f"  {icon}  {p['id']:15s}  {p['name']}")
        print()
        sys.exit(0)

    # Lazy import (only after workspace is set)
    from provider_engine import ProviderRouter
    from repl import GhostREPL, _print_status, _print_banner

    router = ProviderRouter(providers, verbose=True)

    # Status only
    if args.status:
        _print_banner()
        _print_status(router)
        sys.exit(0)

    # One-shot mode
    if args.prompt:
        from tools import TOOL_SYSTEM_PROMPT
        from session import Session
        session = Session(workspace=workspace)
        session.add_user(args.prompt)
        system = "" if args.no_tools else TOOL_SYSTEM_PROMPT + f"\nWorkspace: {workspace}"
        try:
            response, provider_id = router.chat(session.get_messages(system))
            print(response)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Interactive REPL
    repl = GhostREPL(providers, workspace=workspace)
    if args.no_tools:
        repl.agentic_mode = False
    repl.run()


if __name__ == "__main__":
    main()
