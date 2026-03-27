#!/data/data/com.termux/files/usr/bin/bash
# ╔══════════════════════════════════════════════════════╗
# ║  GHOST — Termux Installation Script                  ║
# ║  Free Claude Code clone. Zero cost. Full agentic.   ║
# ╚══════════════════════════════════════════════════════╝

set -e

CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
BOLD="\033[1m"
DIM="\033[2m"
RESET="\033[0m"

GHOST_DIR="$HOME/.ghost"
GHOST_BIN="$PREFIX/bin/ghost"

echo -e "${CYAN}${BOLD}"
echo "  ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗"
echo " ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝"
echo " ██║  ███╗███████║██║   ██║███████╗   ██║   "
echo " ██║   ██║██╔══██║██║   ██║╚════██║   ██║   "
echo " ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   "
echo "  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝   "
echo -e "${RESET}${DIM}  Termux Installation Script${RESET}"
echo ""

# ── Dependencies ──────────────────────────────────────────────
echo -e "${CYAN}[1/4]${RESET} Installing dependencies..."
pkg update -y -q 2>/dev/null || true
pkg install -y python jq curl 2>/dev/null | grep -E "(Installing|already)" || true
echo -e "${GREEN}  ✓ python, jq, curl ready${RESET}"

# ── Install location ───────────────────────────────────────────
echo -e "${CYAN}[2/4]${RESET} Setting up GHOST..."
mkdir -p "$GHOST_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy Python modules
for f in ghost.py provider_engine.py tools.py session.py repl.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$GHOST_DIR/$f"
        echo -e "  ${DIM}copied $f${RESET}"
    else
        echo -e "  ${RED}✗ Missing: $f (run from ghost/ directory)${RESET}"
        exit 1
    fi
done

echo -e "${GREEN}  ✓ Modules installed to $GHOST_DIR${RESET}"

# ── Create launcher ────────────────────────────────────────────
echo -e "${CYAN}[3/4]${RESET} Creating launcher..."
cat > "$GHOST_BIN" << 'LAUNCHER'
#!/data/data/com.termux/files/usr/bin/bash
# GHOST launcher — sources env then runs Python
GHOST_DIR="$HOME/.ghost"

# Source env file if it exists
if [ -f "$GHOST_DIR/.env" ]; then
    set -a
    source "$GHOST_DIR/.env"
    set +a
fi

# Also source from ~/.bashrc exported vars (already in env)
exec python "$GHOST_DIR/ghost.py" "$@"
LAUNCHER

chmod +x "$GHOST_BIN"
echo -e "${GREEN}  ✓ Launcher created: ghost${RESET}"

# ── Environment config ─────────────────────────────────────────
echo -e "${CYAN}[4/4]${RESET} Setting up API key config..."
ENV_FILE="$GHOST_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVTEMPLATE'
# GHOST API Keys — edit this file then restart GHOST
# Priority order: GROQ → CEREBRAS → GEMINI → ... → OLLAMA

# ── Tier 1: Fastest free inference ──────────────────
GROQ_API_KEY=""
GROQ_MODEL="llama-3.3-70b-versatile"

CEREBRAS_API_KEY=""
CEREBRAS_MODEL="llama3.3-70b"

GEMINI_API_KEY=""
GEMINI_MODEL="gemini-2.0-flash"

# ── Tier 2: High quality free/cheap ─────────────────
OPENROUTER_API_KEY=""
OPENROUTER_MODEL="deepseek/deepseek-r1:free"

MISTRAL_API_KEY=""
MISTRAL_MODEL="mistral-small-latest"

TOGETHER_API_KEY=""
TOGETHER_MODEL="meta-llama/Llama-3.3-70B-Instruct-Turbo"

COHERE_API_KEY=""
COHERE_MODEL="command-r7b-12-2024"

# ── Tier 3: Specialty ─────────────────────────────────
HYPERBOLIC_API_KEY=""
HYPERBOLIC_MODEL="meta-llama/Llama-3.3-70B-Instruct"

NVIDIA_API_KEY=""
NVIDIA_MODEL="meta/llama-3.3-70b-instruct"

GITHUB_TOKEN=""
GITHUB_MODEL="gpt-4o-mini"

XAI_API_KEY=""
XAI_MODEL="grok-3-mini"

CLOUDFLARE_ACCOUNT_ID=""
CLOUDFLARE_API_TOKEN=""
CLOUDFLARE_MODEL="@cf/meta/llama-3.3-70b-instruct-fp8-fast"

VENICE_API_KEY=""
VENICE_MODEL="llama-3.3-70b"

MOONSHOT_API_KEY=""
MOONSHOT_MODEL="moonshot-v1-32k"

ZAI_API_KEY=""
ZAI_MODEL="glm-4-flash"

LONGCAT_API_KEY=""
LONGCAT_MODEL="LongCat-Flash-Chat"

# ── Tier 4: Paid (fallback) ───────────────────────────
OPENAI_API_KEY=""
OPENAI_MODEL="gpt-4o-mini"

ANTHROPIC_API_KEY=""
ANTHROPIC_MODEL="claude-haiku-4-5-20251001"

HUGGINGFACE_TOKEN=""
HUGGINGFACE_MODEL="microsoft/Phi-3.5-mini-instruct"

# ── Local (no key needed) ─────────────────────────────
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="llama3.2"

OLLAMA_CLOUD_BASE_URL=""
OLLAMA_CLOUD_API_KEY=""
OLLAMA_CLOUD_MODEL="llama3.2"
ENVTEMPLATE
    echo -e "${GREEN}  ✓ Config created: $ENV_FILE${RESET}"
else
    echo -e "${DIM}  (config already exists, skipping)${RESET}"
fi

# ── Done ───────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  ╔══════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}  ║  GHOST installed successfully! 👻    ║${RESET}"
echo -e "${GREEN}${BOLD}  ╚══════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}Next steps:${RESET}"
echo -e "  ${CYAN}1.${RESET} Edit your API keys:"
echo -e "     ${DIM}nano $ENV_FILE${RESET}"
echo ""
echo -e "  ${CYAN}2.${RESET} Launch GHOST:"
echo -e "     ${DIM}ghost${RESET}"
echo ""
echo -e "  ${CYAN}3.${RESET} One-shot mode:"
echo -e "     ${DIM}ghost \"write a Python web scraper\"${RESET}"
echo ""
echo -e "  ${CYAN}4.${RESET} Force a provider:"
echo -e "     ${DIM}ghost --provider GEMINI${RESET}"
echo ""
echo -e "  ${DIM}At least one API key required. GROQ + GEMINI are easiest (both free).${RESET}"
echo ""
