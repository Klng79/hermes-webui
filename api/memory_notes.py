"""Note-level memory storage — one file per note in memories/notes/."""
import uuid
from pathlib import Path
import frontmatter
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
        result = frontmatter.Frontmatter().read(path.read_text(encoding="utf-8", errors="replace"))
        return result.get("attributes", {}), result.get("body", "")
    except Exception:
        return {}, ""

def _write_note(path, title, content, existing_id=None):
    """Write a note to disk, returns the id."""
    import yaml
    note_id = existing_id or str(uuid.uuid4())[:12]
    metadata = {
        "id": note_id,
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Only try to preserve created_at if the file already exists (update case)
    if path.exists():
        try:
            old_meta, _ = _read_frontmatter(path)
            if "created_at" in old_meta:
                metadata["created_at"] = old_meta["created_at"]
        except Exception:
            pass
    else:
        metadata["created_at"] = metadata["updated_at"]
    fm_text = "---\n" + yaml.dump(metadata, default_flow_style=False) + "---\n" + content
    path.write_text(fm_text, encoding="utf-8")
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
            results.append({
                "id": note_id,
                "title": title,
                "preview": preview,
                "created_at": metadata.get("created_at"),
                "updated_at": metadata.get("updated_at"),
            })
        except Exception:
            continue
    return results

def get_note(note_id):
    """Returns full note dict or None."""
    notes_dir = _get_notes_dir()
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
    _write_note(path, title, content, existing_id=note_id)
    return get_note(note_id)

def update_note(note_id, title, content):
    """Updates and returns the note, or None if not found."""
    notes_dir = _get_notes_dir()
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