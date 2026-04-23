# Memory Notes — Per-Note CRUD Design

## Overview

Convert the memory panel from two monolithic markdown sections ("My Notes" / "User Profile") into a per-note list where each note is an individual file. Users can create, edit, select, and delete notes.

## Storage Model

- **Location:** `~/.hermes/memories/notes/`
- **Format:** One `.md` file per note, using frontmatter for metadata
- **File name:** `{uuid}.md`

### File Format

```markdown
---
id: abc123def456
title: My Note Title
created_at: 2026-04-23T10:30:00Z
updated_at: 2026-04-23T10:30:00Z
---
Note content goes here as markdown.
```

## API Endpoints

Extend the existing `/api/memory` routes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/memory` | List all notes — returns `[{id, title, preview, created_at, updated_at}]` |
| `GET` | `/api/memory/{id}` | Get full note by ID — returns `{id, title, content, created_at, updated_at}` |
| `POST` | `/api/memory` | Create note — body: `{title, content}` |
| `PUT` | `/api/memory/{id}` | Update note — body: `{title, content}` |
| `DELETE` | `/api/memory` | Delete notes — body: `{ids: [...]}` — supports multi-delete |

### Responses

**GET /api/memory**
```json
{
  "notes": [
    {"id": "abc123", "title": "Note Title", "preview": "First 80 chars...", "created_at": "...", "updated_at": "..."}
  ]
}
```

**GET /api/memory/{id}**
```json
{
  "id": "abc123",
  "title": "Note Title",
  "content": "Full markdown content...",
  "created_at": "...",
  "updated_at": "..."
}
```

## Frontend Components

### List View (loadMemory)

- **Header toolbar:** "Add Note" button on left; "Delete Selected" button on right (disabled when nothing selected)
- **Table header row:** checkbox (select all), "Title", "Modified"
- **Note rows:** checkbox, title, content preview (~80 chars), relative time, click row to expand
- **Multi-select:** Shift+click for range, Cmd+click for toggle
- **Empty state:** localized "No notes yet" message with Add Note button

### Inline Form (new/edit)

- Appears at top of list when adding, or replaces row content when editing
- Fields: title input, markdown textarea (full width)
- Buttons: Save / Cancel
- On save: POST or PUT depending on mode; re-render list
- On cancel: collapse form, restore previous state

### Delete Flow

1. User selects notes via checkboxes
2. Delete Selected button enables
3. Click → `showConfirmDialog(danger:true)` with message: "Delete {n} note(s)? This cannot be undone."
4. On confirm: DELETE to `/api/memory` with `{ids: [...]}`; re-render list

### Migration

- On first load, if `~/.hermes/memories/MEMORY.md` or `USER.md` exist, offer one-time import banner: "Import existing notes?"
- Import creates one note per file, title derived from filename

## i18n Strings

```js
memory_notes: "Notes",
memory_add_note: "Add Note",
memory_delete_selected: "Delete Selected",
memory_delete_confirm: "Delete {n} note(s)? This cannot be undone.",
memory_note_title: "Title",
memory_note_content: "Content",
memory_empty: "No notes yet",
memory_import: "Import existing notes?",
memory_import_confirm: "Import your old notes as individual notes?"
```

## Backward Compatibility

- Old `MEMORY.md` / `USER.md` remain untouched — coexistence is fine
- `/api/memory/write` (old endpoint) continues to work as-is for existing callers

## File Changes

- `api/routes.py` — add `_handle_memory_list`, `_handle_memory_get`, `_handle_memory_delete`; adapt existing `_handle_memory_read`
- `api/config.py` — memory home detection unchanged
- `static/panels.js` — replace `loadMemory()` list rendering with new table/list UI
- `static/i18n.js` — add new strings
- `static/index.html` — update memory panel HTML structure
