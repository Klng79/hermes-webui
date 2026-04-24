# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Remotes

- **origin** → `https://github.com/Klng79/hermes-webui.git` (Alex's fork — push here)
- **upstream** → `https://github.com/nesquena/hermes-webui.git` (upstream — pull updates from here)

**Sync workflow:**
```bash
# Pull latest upstream changes
git fetch upstream
git merge upstream/master
# Resolve conflicts if any, preserve local customizations (server restart hook, memory cache fix)
git push origin master
```

## Project Overview

Hermes WebUI is a lightweight, dark-themed browser interface for the Hermes autonomous agent. It provides nearly 1:1 parity with the Hermes CLI experience. The architecture is deliberately simple: a Python stdlib HTTP server with vanilla JS frontend — no build step, no bundler, no framework.

## Running the App

```bash
# Auto-detects Hermes agent, Python venv, and state directories
./start.sh

# Or explicit control
HERMES_WEBUI_PORT=9000 HERMES_WEBUI_PASSWORD=secret ./start.sh

# Health check
curl http://127.0.0.1:8787/health
```

## Running Tests

```bash
pytest tests/ -v --timeout=60
```

Tests use an isolated server on port 8788 with a separate state directory. Production data is never touched. Tests are discovered dynamically — no hardcoded paths.

## Architecture

```
server.py          Thin routing shell + HTTP Handler (~154 lines). Delegates all to api/routes.py
api/
  routes.py        All GET/POST route handlers (the main logic hub)
  streaming.py     SSE engine, run_agent, cancel support
  config.py        Discovery, globals, model detection, reloadable config
  auth.py          Optional password auth, signed cookies
  models.py        Session model + CRUD
  profiles.py      Profile state management
  workspace.py     File ops, workspace helpers, git detection
static/
  index.html       HTML template
  ui.js            DOM helpers, renderMd, tool cards
  messages.js      send(), SSE handlers, streaming
  panels.js        Cron, skills, memory, profiles, settings
  sessions.js      Session CRUD, collapsible groups, search
  commands.js      Slash command autocomplete
  boot.js          Mobile nav, voice input, boot
  style.css        All CSS including themes
```

## Key Design Decisions

**State lives outside the repo** at `~/.hermes/webui-mvp/` (override with `HERMES_WEBUI_STATE_DIR`):
- `sessions/` — one JSON file per session
- `settings.json` — user preferences
- `projects.json` — session groupings
- `workspaces.json` — registered workspace paths

**Sessions are JSON files**, not a database. Each session has: `session_id`, `title`, `workspace`, `model`, `messages[]`, `created_at`, `updated_at`, `pinned`, `archived`, `project_id`.

**No build step**: JS modules are loaded directly via `<script src="">` tags in production order (boot.js last). Changes take effect on reload.

**Themes**: CSS custom properties on `:root[data-theme="name"]`. Theme switching is instant via `document.documentElement.dataset.theme`. See THEMES.md for custom theme guide.

**i18n**: All UI strings in `static/i18n.js`. Language set via Settings panel and persisted to `localStorage`.

**Streaming**: Server-Sent Events (SSE) for live token streaming. Client uses `EventSource` with reconnection on network blips.

## Important Quirks

- `server.py` MUST be run from a Python with Hermes agent dependencies (openai, anthropic, httpx). Use the agent's venv Python, not system Python.
- Per-request env vars (`TERMINAL_CWD`, `HERMES_EXEC_ASK`, `HERMES_SESSION_KEY`, `HERMES_HOME`) are process-global — safe only for single-user, single-concurrent-request deployments.
- `routes.py` has a flat if/elif chain for routing — no framework. The `/api/upload` check must come BEFORE `read_body()` in POST handlers because upload needs `rfile`.
- Workspace panel state is preloaded into `document.documentElement.dataset.workspacePanel` before CSS paints to avoid first-load flash on refresh.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `HERMES_WEBUI_AGENT_DIR` | auto-discovered | Path to hermes-agent checkout |
| `HERMES_WEBUI_PYTHON` | auto-discovered | Python executable |
| `HERMES_WEBUI_HOST` | `127.0.0.1` | Bind address |
| `HERMES_WEBUI_PORT` | `8787` | Port |
| `HERMES_WEBUI_STATE_DIR` | `~/.hermes/webui-mvp` | Sessions and state |
| `HERMES_WEBUI_DEFAULT_WORKSPACE` | `~/workspace` | Default workspace |
| `HERMES_WEBUI_PASSWORD` | *(unset)* | Enable password auth |
| `HERMES_HOME` | `~/.hermes` | Hermes base directory |

## Key Files for Common Tasks

- **Add a new API route**: Edit `api/routes.py` — add to `handle_get`/`handle_post` with appropriate auth check
- **Add a UI panel**: Add to `static/panels.js` and the HTML in `static/index.html`
- **Add a slash command**: Edit `static/commands.js` command registry and add backend handler if needed in `api/routes.py`
- **Add i18n string**: Add to `I18N` object in `static/i18n.js`
- **Add a theme**: Add `:root[data-theme="name"]` block to `static/style.css`
