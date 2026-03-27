#!/usr/bin/env python3
"""
tools.py — Agentic tool execution engine for GHOST
Mirrors Claude Code's tool loop: read/write files, run shell, search, glob.
"""

import os, subprocess, glob, json, re, shutil
from pathlib import Path
from typing import Optional

# ── Tool definitions (sent to LLM as system context) ─────────
TOOL_SYSTEM_PROMPT = """You are GHOST, an expert agentic AI coding assistant running in a terminal.
You help users write, edit, debug, and understand code. You have access to tools.

When you need to use a tool, respond with a JSON block in this exact format (and NOTHING else before or after):

```tool
{
  "tool": "TOOL_NAME",
  "params": { ... }
}
```

Available tools:

1. read_file — Read a file's contents
   params: {"path": "path/to/file"}

2. write_file — Write content to a file (creates or overwrites)
   params: {"path": "path/to/file", "content": "file contents here"}

3. edit_file — Replace a specific string in a file
   params: {"path": "path/to/file", "old": "exact string to find", "new": "replacement string"}

4. run_shell — Execute a shell command (be careful, this is real)
   params: {"command": "ls -la", "cwd": "optional/working/dir"}

5. list_files — List directory contents
   params: {"path": ".", "recursive": false}

6. search_files — Search for text pattern across files
   params: {"pattern": "search term", "path": ".", "file_glob": "*.py"}

7. create_dir — Create a directory
   params: {"path": "path/to/dir"}

8. delete_file — Delete a file (requires confirmation in dangerous cases)
   params: {"path": "path/to/file"}

9. file_info — Get metadata about a file
   params: {"path": "path/to/file"}

10. done — Signal task completion with a summary
    params: {"summary": "What was accomplished"}

Rules:
- Use tools one at a time; wait for results before proceeding
- Always read a file before editing it
- Prefer edit_file over write_file when making targeted changes
- For multi-step tasks, plan first then execute step by step
- After completing all steps, call the done tool with a clear summary
- If unsure about a destructive operation, ask the user first

When NOT using a tool, respond conversationally as normal.
"""

# ── Tool parser ────────────────────────────────────────────────
def parse_tool_call(text: str) -> Optional[dict]:
    """Extract tool JSON block from LLM response."""
    # Match ```tool ... ``` blocks
    match = re.search(r"```tool\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Fallback: look for raw JSON with "tool" key
    match = re.search(r'\{"tool":\s*"[^"]+".*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    return None


# ── Tool executor ──────────────────────────────────────────────
class ToolExecutor:
    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self.max_file_size = 100_000  # 100KB read limit

    def _safe_path(self, path: str) -> Path:
        """Resolve path and ensure it's within workspace (or absolute)."""
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        return p.resolve()

    def execute(self, tool_name: str, params: dict) -> str:
        """Dispatch tool call. Returns result string."""
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "run_shell": self._run_shell,
            "list_files": self._list_files,
            "search_files": self._search_files,
            "create_dir": self._create_dir,
            "delete_file": self._delete_file,
            "file_info": self._file_info,
            "done": self._done,
        }
        
        handler = handlers.get(tool_name)
        if not handler:
            return f"❌ Unknown tool: {tool_name}"
        
        try:
            return handler(**params)
        except TypeError as e:
            return f"❌ Tool parameter error: {e}"
        except Exception as e:
            return f"❌ Tool error: {type(e).__name__}: {e}"

    def _read_file(self, path: str) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"❌ File not found: {path}"
        if p.stat().st_size > self.max_file_size:
            return f"⚠️ File too large ({p.stat().st_size} bytes). Reading first 100KB...\n" + \
                   p.read_text(errors="replace")[:self.max_file_size]
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            # Add line numbers
            numbered = "\n".join(f"{i+1:4d} │ {line}" for i, line in enumerate(lines))
            return f"📄 {path} ({len(lines)} lines)\n```\n{numbered}\n```"
        except Exception as e:
            return f"❌ Read error: {e}"

    def _write_file(self, path: str, content: str) -> str:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        action = "Updated" if existed else "Created"
        lines = content.count("\n") + 1
        return f"✅ {action}: {path} ({lines} lines, {len(content)} chars)"

    def _edit_file(self, path: str, old: str, new: str) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"❌ File not found: {path}"
        content = p.read_text(encoding="utf-8", errors="replace")
        if old not in content:
            return f"❌ Pattern not found in {path}. Use read_file first to verify exact text."
        count = content.count(old)
        new_content = content.replace(old, new, 1)  # Replace first occurrence only
        p.write_text(new_content, encoding="utf-8")
        return f"✅ Edited {path} (replaced {count} occurrence{'s' if count > 1 else ''} of pattern)"

    def _run_shell(self, command: str, cwd: str = None) -> str:
        work_dir = self._safe_path(cwd) if cwd else self.workspace
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            code = result.returncode
            
            response = f"$ {command}\n"
            if out:
                response += f"{out}\n"
            if err:
                response += f"[stderr] {err}\n"
            response += f"[exit: {code}]"
            return response
        except subprocess.TimeoutExpired:
            return f"❌ Command timed out after 60s: {command}"

    def _list_files(self, path: str = ".", recursive: bool = False) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"❌ Path not found: {path}"
        
        if recursive:
            entries = sorted(p.rglob("*"))
        else:
            entries = sorted(p.iterdir())
        
        lines = []
        for entry in entries[:500]:  # cap at 500
            rel = entry.relative_to(p)
            if entry.is_dir():
                lines.append(f"📁 {rel}/")
            else:
                size = entry.stat().st_size
                lines.append(f"📄 {rel} ({_human_size(size)})")
        
        if not lines:
            return f"📂 {path} (empty)"
        return f"📂 {path}/\n" + "\n".join(lines)

    def _search_files(self, pattern: str, path: str = ".", file_glob: str = "*") -> str:
        p = self._safe_path(path)
        results = []
        
        for filepath in p.rglob(file_glob):
            if not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.lower() in line.lower():
                        rel = filepath.relative_to(p)
                        results.append(f"{rel}:{i}: {line.strip()}")
                        if len(results) >= 50:
                            break
            except Exception:
                continue
            if len(results) >= 50:
                break
        
        if not results:
            return f"🔍 No matches for '{pattern}' in {path}/{file_glob}"
        return f"🔍 {len(results)} matches for '{pattern}':\n" + "\n".join(results)

    def _create_dir(self, path: str) -> str:
        p = self._safe_path(path)
        p.mkdir(parents=True, exist_ok=True)
        return f"✅ Directory created: {path}"

    def _delete_file(self, path: str) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"❌ Not found: {path}"
        if p.is_dir():
            shutil.rmtree(p)
            return f"✅ Directory deleted: {path}"
        p.unlink()
        return f"✅ File deleted: {path}"

    def _file_info(self, path: str) -> str:
        p = self._safe_path(path)
        if not p.exists():
            return f"❌ Not found: {path}"
        stat = p.stat()
        import datetime
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"📋 {path}\n"
            f"  Type: {'directory' if p.is_dir() else 'file'}\n"
            f"  Size: {_human_size(stat.st_size)}\n"
            f"  Modified: {mtime}\n"
            f"  Permissions: {oct(stat.st_mode)[-3:]}"
        )

    def _done(self, summary: str) -> str:
        return f"✨ DONE: {summary}"


def _human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
