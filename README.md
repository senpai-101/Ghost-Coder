# 👻 GHOST Coder
### Generative Heuristic Orchestration Shell Terminal

> A free, provider-agnostic Claude Code clone built for Termux.  
> 21 AI providers. Auto-failover. Full agentic loop. Zero cost.

```
  ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
 ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝
 ██║  ███╗███████║██║   ██║███████╗   ██║   
 ██║   ██║██╔══██║██║   ██║╚════██║   ██║   
 ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   
```

---

## ⚡ Features

- **21 AI providers** with automatic failover — if one fails, the next kicks in silently
- **Full agentic loop** — reads/writes files, runs shell commands, edits code
- **Claude Code-style tools** — `read_file`, `write_file`, `edit_file`, `run_shell`, `search_files`, `list_files`
- **Zero dependencies** beyond Python 3 stdlib (no pip required)
- **Termux-native** — works on Android without root
- **Session persistence** — conversation history saved across restarts
- **One-shot + interactive modes**

---

## 📦 Installation (Termux)

```bash
# 1. Clone or download
git clone https://github.com/yourhandle/ghost
cd ghost

# 2. Install
bash install.sh

# 3. Add at least one API key
nano ~/.ghost/.env

# 4. Run
ghost
```

**Minimum setup:** One API key is enough. GROQ and GEMINI are recommended — both have generous free tiers.

---

## 🔑 Provider Priority (auto-failover order)

| # | Provider | Free Tier | Speed |
|---|----------|-----------|-------|
| 1 | **GROQ** | ✓ Generous | ⚡⚡⚡ Fastest |
| 2 | **CEREBRAS** | ✓ Good | ⚡⚡⚡ |
| 3 | **GEMINI** | ✓ Very generous | ⚡⚡ |
| 4 | **OPENROUTER** | ✓ Free models | ⚡⚡ |
| 5 | **MISTRAL** | ✓ Free tier | ⚡⚡ |
| 6 | **TOGETHER** | ✓ Credits | ⚡⚡ |
| 7 | **COHERE** | ✓ Free tier | ⚡⚡ |
| 8 | HYPERBOLIC | Paid | ⚡⚡ |
| 9 | NVIDIA NIM | Credits | ⚡⚡ |
| 10 | GITHUB Models | ✓ Free with GH | ⚡⚡ |
| 11 | XAI (Grok) | Paid | ⚡⚡ |
| 12 | CLOUDFLARE | ✓ Free tier | ⚡ |
| 13 | VENICE | Paid | ⚡ |
| 14 | MOONSHOT | Credits | ⚡ |
| 15 | ZAI (GLM) | ✓ Free | ⚡ |
| 16 | LONGCAT | ✓ Free | ⚡ |
| 17 | OPENAI | Paid | ⚡⚡ |
| 18 | ANTHROPIC | Paid | ⚡⚡ |
| 19 | HUGGINGFACE | ✓ Free | ⚡ |
| 20 | **OLLAMA** | ✓ Local/Free | Varies |
| 21 | OLLAMA Cloud | Varies | Varies |

---

## 💻 Usage

### Interactive REPL
```bash
ghost
ghost --workspace ~/myproject
```

### One-shot
```bash
ghost "write a Python web scraper for HackerNews"
ghost "explain this error: segfault at 0x0"
ghost --no-tools "what is async/await"
```

### Force a provider
```bash
ghost --provider GEMINI
ghost --provider OPENROUTER
ghost --provider OLLAMA    # Use local Ollama
```

### Override model
```bash
ghost --model GROQ mixtral-8x7b-32768
ghost --model OPENROUTER deepseek/deepseek-coder-v2:free
ghost --model OLLAMA codellama
```

### Check status
```bash
ghost --status             # Show all providers + key status
ghost --list-providers     # List provider IDs
```

---

## 🛠️ REPL Commands

| Command | Description |
|---------|-------------|
| `/status` | Show all providers + which have keys |
| `/provider GEMINI` | Switch primary provider |
| `/model GROQ mixtral-8x7b` | Switch provider + model |
| `/tools` | Toggle agentic tool use on/off |
| `/stats` | Session stats (tokens, turns, providers) |
| `/clear` | Clear conversation context |
| `/sessions` | List saved sessions |
| `/cd <path>` | Change workspace directory |
| `/help` | Show all commands |
| `/exit` | Save and quit |

---

## 🤖 Agentic Tool Loop

GHOST runs a full agentic loop like Claude Code:

```
User input
    ↓
LLM generates response
    ↓
Does it contain a tool call?
  ├── YES → Execute tool → Feed result back → Loop
  └── NO  → Print response → Wait for next input
```

Available tools the AI can use autonomously:
- `read_file` — Read any file with line numbers
- `write_file` — Create or overwrite files
- `edit_file` — Targeted string replacement (safer than full rewrite)
- `run_shell` — Execute shell commands (with 60s timeout)
- `list_files` — Directory listing (recursive or flat)
- `search_files` — Grep-style search across files
- `create_dir` — Create directories
- `delete_file` — Delete files or directories
- `file_info` — File metadata (size, permissions, mtime)
- `done` — Signal task completion with summary

---

## 📁 File Structure

```
~/.ghost/
├── ghost.py           # Entry point + provider registry
├── provider_engine.py # API layer + failover router
├── tools.py           # Agentic tool execution
├── session.py         # Conversation history + persistence
├── repl.py            # Interactive shell + display
├── .env               # Your API keys (edit this!)
└── sessions/          # Saved conversation sessions
    └── <id>.json
```

---

## 🔧 API Key Sources (all free tiers)

| Provider | Get Key |
|----------|---------|
| GROQ | https://console.groq.com |
| CEREBRAS | https://cloud.cerebras.ai |
| GEMINI | https://aistudio.google.com |
| OPENROUTER | https://openrouter.ai |
| MISTRAL | https://console.mistral.ai |
| TOGETHER | https://api.together.xyz |
| COHERE | https://dashboard.cohere.com |
| NVIDIA NIM | https://build.nvidia.com |
| GITHUB | https://github.com/settings/tokens |
| CLOUDFLARE | https://dash.cloudflare.com |
| HUGGINGFACE | https://huggingface.co/settings/tokens |
| ZAI | https://bigmodel.cn |

---

## 🧩 Architecture Notes

- **Zero pip dependencies** — uses only Python stdlib (`urllib`, `json`, `subprocess`, `pathlib`)
- **jq optional** — only needed for the legacy bash `ai()` wrapper in your shell config
- **Provider failover** — HTTP 401/403 permanently blacklists a provider this session; rate limits trigger retry on next call
- **Context window management** — auto-trims oldest messages to stay within ~60K chars
- **Workspace isolation** — file tools operate relative to `--workspace` (default: current dir)

---

## 💡 Tips

```bash
# Fastest setup: just GROQ + GEMINI covers most use cases
export GROQ_API_KEY="gsk_..."
export GEMINI_API_KEY="AIza..."
ghost

# Use Ollama for fully offline operation
ollama pull codellama
ghost --provider OLLAMA

# Pipe files directly
cat myfile.py | ghost "review this code for bugs"

# Use as a shell tool in scripts
RESULT=$(ghost --no-tools "generate a UUID")
echo $RESULT
```

---

## License

MIT — hack it, fork it, ship it. 👻
