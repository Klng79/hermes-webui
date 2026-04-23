# Memory Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-section memory panel (My Notes / User Profile) with a per-note list where each note is a separate file, with CRUD and multi-select delete.

**Architecture:** Notes stored as individual `.md` files in `~/.hermes/memories/notes/`. API extends `/api/memory` with note-level CRUD. Frontend replaces `loadMemory()` with a list/checkbox UI.

**Tech Stack:** Vanilla JS (no framework), Python stdlib, SSE for streaming already in place.

---

## File Map

| File | Responsibility |
|------|---------------|
| `api/routes.py` | Add 5 new handlers; update GET/POST dispatch |
| `static/i18n.js` | Add 8 new translation strings |
| `static/panels.js` | Rewrite `loadMemory()`; add `saveNote()`, `deleteSelectedNotes()`, `showNoteForm()` |
| `static/index.html` | Update `#memoryPanel` HTML container |

---

## Task 1: Add i18n Strings

**Files:** Modify `static/i18n.js`

Add these keys to the `en` locale (lines ~452-457 area, after `no_notes_yet`):

```js
memory_notes: 'Notes',
memory_add_note: 'Add Note',
memory_delete_selected: 'Delete Selected',
memory_delete_confirm: 'Delete {n} note(s)? This cannot be undone.',
memory_note_title: 'Title',
memory_note_content: 'Content',
memory_empty: 'No notes yet. Click "Add Note" to create one.',
memory_updated: 'Note saved',
memory_created: 'Note created',
memory_deleted: 'Note(s) deleted',
```

- [ ] **Step 1: Add the new strings to `static/i18n.js` in the `en` locale, after `no_notes_yet`**

Run: `grep -n "no_notes_yet" static/i18n.js | head -3` to find the line numbers, then Edit to add after the English `no_notes_yet` entry.

---

## Task 2: Backend — Note Storage Helpers

**Files:** Create `api/memory_notes.py` (new file)

- [ ] **Step 1: Write the new file with note CRUD helpers**

```python
"""Note-level memory storage — one file per note in memories/notes/."""
import uuid
from pathlib import Path
import frontmatter  # already a hermes dependency
from datetime import datetime, timezone

NOTES_DIR_NAME = "notes"

def _get_notes_dir():
    try:
        from api.profiles import get_active_hermes_home
        mem_dir = get_active_hermes_home() / "memories"
    except ImportError:
        mem_dir = Path.home() / ".hermes" / "memories"
    notes_dir = mem_dir / NOTES_DIR_NAME
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir

def _read_frontmatter(path):
    """Returns (metadata, content) from a frontmatter .md file."""
    try:
        post = frontmatter.loads(path.read_text(encoding="utf-8", errors="replace"))
        return post.metadata, post.content
    except Exception:
        return {}, ""

def _write_note(path, title, content, existing_id=None):
    """Write a note to disk, returns the id."""
    note_id = existing_id or str(uuid.uuid4())[:12]
    metadata = {
        "id": note_id,
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not existing_id:
        metadata["created_at"] = metadata["updated_at"]
    else:
        # Preserve created_at on update
        try:
            old_meta, _ = _read_frontmatter(path)
            if "created_at" in old_meta:
                metadata["created_at"] = old_meta["created_at"]
        except Exception:
            pass
    post = frontmatter.Post(content, **metadata)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return note_id

def list_notes():
    """Returns list of note summaries (id, title, preview, created_at, updated_at)."""
    notes_dir = _get_notes_dir()
    results = []
    for path in sorted(notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            metadata, content = _read_frontmatter(path)
            note_id = metadata.get("id", path.stem)
            title = metadata.get("title", "Untitled")
            preview = content[:80].strip() if content else ""
            created_at = metadata.get("created_at")
            updated_at = metadata.get("updated_at")
            results.append({
                "id": note_id,
                "title": title,
                "preview": preview,
                "created_at": created_at,
                "updated_at": updated_at,
            })
        except Exception:
            continue
    return results

def get_note(note_id):
    """Returns full note dict or None."""
    notes_dir = _get_notes_dir()
    # Find by id in frontmatter
    for path in notes_dir.glob("*.md"):
        try:
            metadata, content = _read_frontmatter(path)
            if metadata.get("id") == note_id:
                return {
                    "id": note_id,
                    "title": metadata.get("title", "Untitled"),
                    "content": content,
                    "created_at": metadata.get("created_at"),
                    "updated_at": metadata.get("updated_at"),
                }
        except Exception:
            continue
    return None

def create_note(title, content):
    """Creates and returns the new note."""
    notes_dir = _get_notes_dir()
    note_id = str(uuid.uuid4())[:12]
    path = notes_dir / f"{note_id}.md"
    _write_note(path, title, content)
    return get_note(note_id)

def update_note(note_id, title, content):
    """Updates and returns the note, or None if not found."""
    notes_dir = _get_notes_dir()
    # Find the file with matching id
    for path in notes_dir.glob("*.md"):
        try:
            metadata, _ = _read_frontmatter(path)
            if metadata.get("id") == note_id:
                _write_note(path, title, content, existing_id=note_id)
                return get_note(note_id)
        except Exception:
            continue
    return None

def delete_notes(note_ids):
    """Deletes all notes matching the given ids. Returns count deleted."""
    notes_dir = _get_notes_dir()
    deleted = 0
    for path in notes_dir.glob("*.md"):
        try:
            metadata, _ = _read_frontmatter(path)
            if metadata.get("id") in note_ids:
                path.unlink(missing_ok=True)
                deleted += 1
        except Exception:
            continue
    return deleted
```

- [ ] **Step 2: Run a quick sanity check**

Run: `cd /Users/alexng/hermes-webui && python3 -c "from api.memory_notes import list_notes, create_note; print('import ok')"`

Expected: `import ok`

---

## Task 3: Backend — API Handlers and Route Dispatch

**Files:** Modify `api/routes.py`

Add these imports near the top (after existing imports):

```python
from api.memory_notes import (
    list_notes,
    get_note,
    create_note,
    update_note,
    delete_notes,
)
```

- [ ] **Step 1: Add the import line after the other api imports**

Find the `from api.helpers` import block and add the new import below it.

- [ ] **Step 2: Add note CRUD handlers — insert after `_handle_memory_read` (~line 2529)**

```python
def _handle_memory_list(handler):
    """GET /api/memory — list all notes."""
    notes = list_notes()
    return j(handler, {"notes": notes})


def _handle_memory_get(handler, note_id):
    """GET /api/memory/{id} — get single note."""
    note = get_note(note_id)
    if note is None:
        return bad(handler, "Note not found", 404)
    return j(handler, note)


def _handle_memory_create(handler, body):
    """POST /api/memory — create a new note."""
    try:
        require(body, "title", "content")
    except ValueError as e:
        return bad(handler, str(e))
    title = str(body["title"]).strip()
    content = str(body.get("content", ""))
    if not title:
        return bad(handler, "title is required")
    note = create_note(title, content)
    return j(handler, note, status=201)


def _handle_memory_update(handler, body, note_id):
    """PUT /api/memory/{id} — update a note."""
    try:
        require(body, "title", "content")
    except ValueError as e:
        return bad(handler, str(e))
    note = update_note(note_id, str(body["title"]).strip(), str(body.get("content", "")))
    if note is None:
        return bad(handler, "Note not found", 404)
    return j(handler, note)


def _handle_memory_delete(handler, body):
    """DELETE /api/memory — delete notes by ids."""
    try:
        require(body, "ids")
    except ValueError as e:
        return bad(handler, str(e))
    ids = body["ids"]
    if not isinstance(ids, list):
        return bad(handler, "ids must be a list")
    deleted = delete_notes(ids)
    return j(handler, {"ok": True, "deleted": deleted})
```

- [ ] **Step 3: Update GET dispatch — modify the `/api/memory` check (~line 1083)**

The existing check `if parsed.path == "/api/memory":` needs to be replaced with routing to list or get-by-id:

```python
    # ── Memory Notes API (GET) ──
    if parsed.path == "/api/memory":
        # /api/memory/{id} vs /api/memory
        if parsed.path.startswith("/api/memory/"):
            note_id = parsed.path[len("/api/memory/"):]
            return _handle_memory_get(handler, note_id)
        return _handle_memory_list(handler)
```

Replace the existing `if parsed.path == "/api/memory": return _handle_memory_read(handler)` block.

- [ ] **Step 4: Update POST dispatch — add new routes (~line 1454, before memory/write)**

```python
    # ── Memory Notes API (POST) ──
    if parsed.path == "/api/memory":
        return _handle_memory_create(handler, body)
    if parsed.path.startswith("/api/memory/") and method == "PUT":
        note_id = parsed.path[len("/api/memory/"):]
        return _handle_memory_update(handler, body, note_id)
    if parsed.path == "/api/memory/delete":
        return _handle_memory_delete(handler, body)
```

Note: Keep `if parsed.path == "/api/memory/write":` for backward compat with existing callers (the old flat-file memory write).

- [ ] **Step 5: Run the health check**

Run: `curl http://127.0.0.1:8787/api/memory`

Expected: `{"notes": []}`

---

## Task 4: Frontend — Rewrite `loadMemory()` in panels.js

**Files:** Modify `static/panels.js` (~line 1240)

First, add a helper function `relativeTime` near the memory section (or in the helpers area at top of panels.js):

```javascript
function relativeTime(isoString) {
  if (!isoString) return '';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  const days = Math.floor(hrs / 24);
  if (days < 30) return days + 'd ago';
  return new Date(isoString).toLocaleDateString();
}
```

Now replace the entire `loadMemory` function (lines 1241-1267) with the new list-based version:

```javascript
// ── Memory Notes ───────────────────────────────────────────────────────────────
let _selectedNotes = new Set();
let _editingNoteId = null;  // null = new note, string = existing id

async function loadMemory(force) {
  const panel = $('memoryPanel');
  _selectedNotes.clear();
  _editingNoteId = null;
  try {
    const data = await api('/api/memory');
    renderMemoryList(data.notes || []);
  } catch(e) {
    panel.innerHTML = `<div style="color:var(--accent);font-size:12px">${esc(t('error_prefix'))}${esc(e.message)}</div>`;
  }
}

function renderMemoryList(notes) {
  const panel = $('memoryPanel');
  const hasNotes = notes.length > 0;
  const anySelected = _selectedNotes.size > 0;

  let html = `<div class="memory-toolbar">
    <button class="btn-ghost" id="memAddBtn" onclick="showNoteForm(null)">${li('plus',14)} ${esc(t('memory_add_note'))}</button>
    <button class="btn-ghost danger" id="memDelBtn" onclick="deleteSelectedNotes()" ${anySelected ? '' : 'disabled'}>${li('trash',14)} ${esc(t('memory_delete_selected'))}</button>
  </div>`;

  if (!hasNotes) {
    html += `<div class="memory-empty">${esc(t('memory_empty'))}</div>`;
  } else {
    html += `<div class="memory-list">`;
    for (const note of notes) {
      const checked = _selectedNotes.has(note.id) ? 'checked' : '';
      const isEditing = _editingNoteId === note.id;
      html += `
      <div class="memory-note-row ${isEditing ? 'editing' : ''}" data-id="${esc(note.id)}">
        <div class="memory-note-header" onclick="toggleNoteRow('${esc(note.id)}')">
          <input type="checkbox" class="mem-check" data-id="${esc(note.id)}" onclick="event.stopPropagation();toggleNoteSelect('${esc(note.id)}')" ${checked}>
          <span class="mem-title">${esc(note.title || 'Untitled')}</span>
          <span class="mem-time">${esc(relativeTime(note.updated_at))}</span>
          <span class="mem-toggle">${isEditing ? li('chevron-up',14) : li('chevron-down',14)}</span>
        </div>
        ${isEditing ? renderNoteForm(note) : `
        <div class="mem-preview">${esc(note.preview || '')}</div>`}
      </div>`;
    }
    html += `</div>`;
  }

  // If adding new note, prepend form
  if (_editingNoteId === null && panel.querySelector('.mem-new-form')) {
    // Keep form visible
  }
  panel.innerHTML = html;

  // Attach checkbox listeners
  panel.querySelectorAll('.mem-check').forEach(cb => {
    cb.addEventListener('change', () => toggleNoteSelect(cb.dataset.id));
  });
}

function renderNoteForm(note) {
  const isNew = !note || note === true;
  const title = (note && note.title) ? esc(note.title) : '';
  const content = (note && note.content) ? esc(note.content) : '';
  return `
  <div class="mem-edit-form ${isNew ? 'mem-new-form' : ''}">
    <input class="mem-form-title" type="text" id="memFormTitle" placeholder="${esc(t('memory_note_title'))}" value="${title}">
    <textarea class="mem-form-content" id="memFormContent" placeholder="${esc(t('memory_note_content'))}">${content}</textarea>
    <div class="mem-form-actions">
      <button class="btn-primary" onclick="saveNote(${note && note.id ? "'" + esc(note.id) + "'" : 'null'})">${esc(t('save_title'))}</button>
      <button class="btn-ghost" onclick="cancelNoteEdit()">${esc(t('cancel_title'))}</button>
    </div>
  </div>`;
}

function showNoteForm(noteId) {
  if (noteId === null) {
    _editingNoteId = null;  // new note
    const panel = $('memoryPanel');
    const toolbar = panel.querySelector('.memory-toolbar');
    const formHtml = `<div class="memory-note-row editing"><div class="mem-edit-form mem-new-form">${renderNoteForm(true)}</div></div>`;
    toolbar.insertAdjacentHTML('afterend', formHtml);
    $('memFormTitle')?.focus();
  } else {
    _editingNoteId = noteId;
    // Re-render to show the form inline
    loadMemory();
  }
}

async function saveNote(noteId) {
  const title = $('memFormTitle')?.value.trim();
  const content = $('memFormContent')?.value || '';
  if (!title) { showToast(t('error_prefix') + 'Title required'); return; }
  try {
    if (noteId) {
      await api(`/api/memory/${noteId}`, { method: 'PUT', body: JSON.stringify({ title, content }) });
      showToast(t('memory_updated'));
    } else {
      await api('/api/memory', { method: 'POST', body: JSON.stringify({ title, content }) });
      showToast(t('memory_created'));
    }
    _editingNoteId = null;
    loadMemory();
  } catch(e) { showToast(t('save_failed') + e.message); }
}

function cancelNoteEdit() {
  _editingNoteId = null;
  loadMemory();
}

function toggleNoteRow(noteId) {
  if (_editingNoteId === noteId) {
    _editingNoteId = null;
  } else {
    _editingNoteId = noteId;
    // Show inline form for editing
    loadMemory();
  }
}

function toggleNoteSelect(noteId) {
  if (_selectedNotes.has(noteId)) {
    _selectedNotes.delete(noteId);
  } else {
    _selectedNotes.add(noteId);
  }
  updateDeleteButton();
}

function updateDeleteButton() {
  const btn = $('memDelBtn');
  if (!btn) return;
  const any = _selectedNotes.size > 0;
  btn.disabled = !any;
}

async function deleteSelectedNotes() {
  const n = _selectedNotes.size;
  if (n === 0) return;
  const confirmed = await showConfirmDialog({
    title: t('memory_delete_selected'),
    message: t('memory_delete_confirm', n),
    confirmLabel: t('delete_title'),
    danger: true,
    focusCancel: true
  });
  if (!confirmed) return;
  try {
    await api('/api/memory/delete', { method: 'POST', body: JSON.stringify({ ids: [..._selectedNotes] }) });
    showToast(t('memory_deleted'));
    _selectedNotes.clear();
    loadMemory();
  } catch(e) { showToast(t('delete_failed') + e.message); }
}
```

- [ ] **Step 1: Replace `loadMemory` function in `static/panels.js`**

Use Edit to replace lines 1240-1267 (the old `loadMemory` function) with the new implementation above.

---

## Task 5: Frontend — CSS for Memory List

**Files:** Modify `static/style.css`

Add after any existing `.memory-*` styles (search for `memory-section`):

```css
/* Memory Notes list */
.memory-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.memory-toolbar .danger { color: var(--accent); }
.memory-toolbar .danger:disabled { opacity: 0.4; cursor: not-allowed; }

.memory-list { display: flex; flex-direction: column; }

.memory-note-row {
  border-bottom: 1px solid var(--border);
}
.memory-note-row.editing { background: var(--bg-hover); }
.memory-note-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
}
.memory-note-header:hover { background: var(--bg-hover); }
.mem-check { width: 16px; height: 16px; cursor: pointer; flex-shrink: 0; }
.mem-title { flex: 1; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mem-time { font-size: 11px; color: var(--text-muted); flex-shrink: 0; }
.mem-toggle { color: var(--text-muted); flex-shrink: 0; }
.mem-preview {
  padding: 0 12px 10px 36px;
  font-size: 13px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mem-edit-form {
  padding: 10px 12px 12px 36px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mem-form-title {
  width: 100%;
  padding: 6px 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 14px;
}
.mem-form-content {
  width: 100%;
  min-height: 120px;
  padding: 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 13px;
  resize: vertical;
  font-family: inherit;
}
.mem-form-actions { display: flex; gap: 8px; }
.memory-empty {
  padding: 32px 12px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}
```

- [ ] **Step 1: Append the CSS above to `static/style.css`**

---

## Task 6: HTML — Memory Panel Container

**Files:** Modify `static/index.html` (~lines 110-127)

The current `#memoryPanel` container should be a simple div (no internal structure needed since JS will fill it):

```html
<div id="memoryPanel" class="panel-content"></div>
```

- [ ] **Step 1: Verify the `#memoryPanel` div is present in `static/index.html`**

Run: `grep -n "memoryPanel" static/index.html`

Expected: A div with `id="memoryPanel"`. If it has existing inner HTML (like section divs), replace with just the empty div.

---

## Task 7: End-to-End Test

- [ ] **Step 1: Start the server and open the Memory panel**

Run: `./start.sh` then navigate to the Memory tab.

- [ ] **Step 2: Create a note**

Click "Add Note", fill in title and content, click Save.

Expected: Note appears in the list.

- [ ] **Step 3: Edit a note**

Click a note row → form expands inline → change title → Save.

Expected: Note updates in the list.

- [ ] **Step 4: Delete a note**

Select checkbox → Delete Selected → confirm dialog → OK.

Expected: Note disappears from list.

- [ ] **Step 5: Multi-select delete**

Select 2+ notes → Delete Selected → confirm → OK.

Expected: All selected notes deleted.

- [ ] **Step 6: Run tests**

Run: `pytest tests/ -v --timeout=60 -k memory`

Expected: No regressions in existing tests.

---

## Spec Coverage Check

| Spec requirement | Task |
|-----------------|------|
| One file per note in `memories/notes/` | Task 2 |
| `GET /api/memory` → list | Task 3 |
| `GET /api/memory/{id}` → get | Task 3 |
| `POST /api/memory` → create | Task 3 |
| `PUT /api/memory/{id}` → update | Task 3 |
| `DELETE /api/memory` → delete | Task 3 |
| Checkbox per row, multi-select | Task 4 |
| Add button + inline form | Task 4 |
| Click row to edit inline | Task 4 |
| Delete with confirmation | Task 4 |
| i18n strings | Task 1 |
| CSS for new UI | Task 5 |
