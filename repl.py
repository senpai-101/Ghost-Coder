#!/usr/bin/env python3
"""
repl.py — Interactive REPL and agentic loop for GHOST
The main event loop: input → LLM → tool execution → repeat
"""

import os, sys, re, time, json
from pathlib import Path

from provider_engine import ProviderRouter
from tools import ToolExecutor, parse_tool_call, TOOL_SYSTEM_PROMPT
from session import Session, list_sessions

try:
    import readline  # Enable arrow keys + history in terminal
except ImportError:
    pass

# ── Colors ─────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    MAGENTA = "\033[35m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    BLUE    = "\033[34m"
    WHITE   = "\033[97m"

def c(color, text): return f"{color}{text}{C.RESET}"

MAX_TOOL_ITERATIONS = 20  # Safety cap on agentic loops


# ── GHOST REPL ─────────────────────────────────────────────────
class GhostREPL:
    def __init__(self, providers: list, workspace: str = "."):
        self.router = ProviderRouter(providers, verbose=True)
        self.executor = ToolExecutor(workspace)
        self.session = Session(workspace=workspace)
        self.workspace = str(Path(workspace).resolve())
        self.agentic_mode = True  # Enable tool use by default

    # ── Agentic loop ───────────────────────────────────────────
    def _agentic_loop(self, user_input: str) -> str:
        """
        Core loop: send → check for tool call → execute → repeat.
        Returns final response text.
        """
        self.session.add_user(user_input)
        
        for iteration in range(MAX_TOOL_ITERATIONS):
            # Build system prompt
            system = TOOL_SYSTEM_PROMPT + f"\n\nWorkspace: {self.workspace}"
            
            try:
                response, provider_id = self.router.chat(
                    self.session.get_messages(system)
                )
            except RuntimeError as e:
                return c(C.RED, f"❌ {e}")

            self.session.add_assistant(response, provider_id)
            _print_provider_tag(provider_id)
            
            # Check for tool call
            tool_call = parse_tool_call(response) if self.agentic_mode else None
            
            if tool_call is None:
                # No tool — this is the final response
                return response
            
            # Strip the tool block from displayed response
            display = re.sub(r"```tool.*?```", "", response, flags=re.DOTALL).strip()
            if display:
                _print_assistant(display)
            
            # Execute tool
            tool_name = tool_call.get("tool", "")
            params = tool_call.get("params", {})
            
            _print_tool_call(tool_name, params)
            
            if tool_name == "done":
                result = self.executor.execute("done", params)
                return result
            
            result = self.executor.execute(tool_name, params)
            _print_tool_result(result)
            
            # Feed result back into context
            self.session.add_tool_result(result)
        
        return c(C.YELLOW, "⚠️  Max tool iterations reached. Stopping agentic loop.")

    # ── Pure chat (no tools) ───────────────────────────────────
    def _chat(self, user_input: str) -> str:
        self.session.add_user(user_input)
        try:
            response, provider_id = self.router.chat(
                self.session.get_messages()
            )
        except RuntimeError as e:
            return c(C.RED, f"❌ {e}")
        self.session.add_assistant(response, provider_id)
        _print_provider_tag(provider_id)
        return response

    # ── Command handler ────────────────────────────────────────
    def _handle_command(self, cmd: str) -> bool:
        """Returns True if command was handled (don't send to LLM)."""
        parts = cmd.strip().split(None, 1)
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if verb in ("/exit", "/quit", "/q"):
            self.session.save()
            print(c(C.MAGENTA, "\n  👻 GHOST out. Session saved.\n"))
            sys.exit(0)

        elif verb == "/help":
            _print_help()

        elif verb == "/status":
            _print_status(self.router)

        elif verb == "/clear":
            self.session.clear()
            print(c(C.GREEN, "  ✓ Context cleared"))

        elif verb == "/stats":
            stats = self.session.stats()
            print(c(C.CYAN, f"""
  Session : {stats['session_id']}
  Turns   : {stats['turns']}
  Context : {stats['messages_in_context']} messages (~{stats['estimated_tokens']} tokens)
  Used    : {', '.join(stats['providers_used']) or 'none yet'}
  WS      : {stats['workspace']}"""))

        elif verb == "/provider":
            if arg:
                self._switch_provider(arg.strip().upper())
            else:
                _print_status(self.router)

        elif verb == "/tools":
            self.agentic_mode = not self.agentic_mode
            state = c(C.GREEN, "ON") if self.agentic_mode else c(C.YELLOW, "OFF")
            print(f"  🔧 Agentic tool use: {state}")

        elif verb == "/sessions":
            sessions = list_sessions()
            if not sessions:
                print(c(C.DIM, "  No saved sessions"))
            for s in sessions:
                import datetime
                t = datetime.datetime.fromtimestamp(s["last_active"]).strftime("%m/%d %H:%M")
                print(f"  {c(C.CYAN, s['id'])}  {s['turns']} turns  {t}  {s['workspace']}")

        elif verb == "/cd":
            if arg and Path(arg).exists():
                os.chdir(arg)
                self.workspace = str(Path(arg).resolve())
                self.executor.workspace = Path(self.workspace)
                print(c(C.GREEN, f"  ✓ Workspace: {self.workspace}"))
            else:
                print(c(C.RED, f"  ❌ Directory not found: {arg}"))

        elif verb == "/model":
            if arg:
                pid, *rest = arg.split(None, 1)
                model = rest[0] if rest else None
                self._switch_provider(pid.upper(), model)
            else:
                _print_status(self.router)

        else:
            return False  # Not a command
        
        return True

    def _switch_provider(self, pid: str, model: str = None):
        # Find provider
        from ghost import PROVIDERS
        for p in PROVIDERS:
            if p["id"] == pid:
                # Override environment model if specified
                if model:
                    env_key = p.get("env_model")
                    if env_key:
                        os.environ[env_key] = model
                # Move to front of router
                others = [x for x in self.router.providers if x["id"] != pid]
                self.router.providers = [p] + others
                m = model or os.environ.get(p.get("env_model", ""), p["default_model"])
                print(c(C.GREEN, f"  ✓ Primary provider: {p['name']} [{m}]"))
                return
        print(c(C.RED, f"  ❌ Unknown provider: {pid}"))

    # ── Main REPL ──────────────────────────────────────────────
    def run(self):
        _print_banner()
        print(c(C.DIM, f"  Workspace: {self.workspace}"))
        print(c(C.DIM, f"  Type /help for commands, /status to see providers\n"))

        while True:
            try:
                prompt = f"\n{c(C.MAGENTA, '▸')} "
                user_input = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                self.session.save()
                print(c(C.MAGENTA, "\n  👻 GHOST out.\n"))
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                self._handle_command(user_input[1:] if user_input[1:] else "help")
                continue

            # Agentic or chat
            if self.agentic_mode:
                response = self._agentic_loop(user_input)
            else:
                response = self._chat(user_input)
            
            _print_assistant(response)
            self.session.save()


# ── Pretty printers ────────────────────────────────────────────
def _print_banner():
    print(f"""
{C.CYAN}{C.BOLD}
  ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
 ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝
 ██║  ███╗███████║██║   ██║███████╗   ██║   
 ██║   ██║██╔══██║██║   ██║╚════██║   ██║   
 ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   
{C.RESET}{C.DIM}  Free · Multi-provider · Agentic · Termux-native{C.RESET}
""")

def _print_assistant(text: str):
    # Syntax highlight code blocks
    def highlight_code(m):
        lang = m.group(1) or ""
        code = m.group(2)
        return f"{C.DIM}```{lang}{C.RESET}\n{C.WHITE}{code}{C.RESET}\n{C.DIM}```{C.RESET}"
    
    highlighted = re.sub(r"```(\w*)\n(.*?)```", highlight_code, text, flags=re.DOTALL)
    
    print(f"\n{C.CYAN}╭─ GHOST{C.RESET}")
    for line in highlighted.splitlines():
        print(f"{C.CYAN}│{C.RESET} {line}")
    print(f"{C.CYAN}╰{'─'*40}{C.RESET}")

def _print_provider_tag(provider_id: str):
    print(f"  {C.DIM}[via {provider_id}]{C.RESET}")

def _print_tool_call(name: str, params: dict):
    param_str = ", ".join(f"{k}={repr(v)[:40]}" for k, v in params.items())
    print(f"\n  {C.YELLOW}⚙  {name}({param_str}){C.RESET}")

def _print_tool_result(result: str):
    lines = result.splitlines()[:20]  # Show first 20 lines
    for line in lines:
        print(f"  {C.DIM}│ {line}{C.RESET}")
    if len(result.splitlines()) > 20:
        print(f"  {C.DIM}│ ... ({len(result.splitlines())} lines total){C.RESET}")

def _print_status(router: ProviderRouter):
    print(f"\n  {C.BOLD}Provider Status:{C.RESET}")
    for s in router.status():
        if s["has_key"]:
            icon = c(C.RED, "✗ FAIL") if s["failed"] else c(C.GREEN, "✓ READY")
        else:
            icon = c(C.DIM, "· NO KEY")
        print(f"  {icon}  {s['id']:15s}  {s['name']}")
    print()

def _print_help():
    print(f"""
{C.BOLD}  GHOST Commands:{C.RESET}

  {C.CYAN}/status{C.RESET}              Show all providers + key status
  {C.CYAN}/provider <ID>{C.RESET}       Switch primary provider (e.g. /provider GEMINI)
  {C.CYAN}/model <ID> [name]{C.RESET}   Switch provider + override model name
  {C.CYAN}/tools{C.RESET}               Toggle agentic tool use on/off
  {C.CYAN}/stats{C.RESET}               Show session statistics
  {C.CYAN}/clear{C.RESET}               Clear conversation context
  {C.CYAN}/sessions{C.RESET}            List saved sessions
  {C.CYAN}/cd <path>{C.RESET}           Change workspace directory
  {C.CYAN}/help{C.RESET}                This menu
  {C.CYAN}/exit{C.RESET}                Save and quit

{C.BOLD}  Provider IDs:{C.RESET}
  GROQ, CEREBRAS, GEMINI, OPENROUTER, MISTRAL,
  TOGETHER, COHERE, HYPERBOLIC, NVIDIA, GITHUB,
  XAI, CLOUDFLARE, VENICE, MOONSHOT, ZAI,
  LONGCAT, OPENAI, ANTHROPIC, HUGGINGFACE,
  OLLAMA, OLLAMA_CLOUD

{C.BOLD}  Examples:{C.RESET}
  /provider GEMINI
  /model OPENROUTER deepseek/deepseek-coder-v2:free
  /model OLLAMA codellama
""")
