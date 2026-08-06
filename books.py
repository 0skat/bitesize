"""Copy EPUBs to the macOS iCloud Books library for iPhone sync."""

import shutil
from pathlib import Path

from config import console
from settings_store import Settings

_CANDIDATE_DIRS = (
    Path.home() / "Library/Mobile Documents/iCloud~com~apple~iBooks/Documents",
    Path.home() / "Library/Mobile Documents/com~apple~iBooks/Documents",
)


def resolve_icloud_books_dir(settings: Settings | None = None) -> Path | None:
    """Return the iCloud Books Documents folder, or None if unavailable."""
    override = ""
    if settings is not None:
        override = (settings.icloud_books_dir or "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_dir() else None
    for path in _CANDIDATE_DIRS:
        if path.is_dir():
            return path
    return None


def copy_to_icloud_books(epub_path: Path, settings: Settings | None = None) -> bool:
    """
    Copy epub_path into the iCloud Books library.

    Returns True on success, False on failure (with a console message).
    Never raises — delivery is best-effort and should not abort the run.
    """
    if settings is None:
        from config import get_settings

        settings = get_settings()

    if not epub_path.exists():
        console.print(
            f"  [yellow]⚠  iCloud Books copy skipped — file not found: {epub_path}[/yellow]"
        )
        return False

    dest_dir = resolve_icloud_books_dir(settings)
    if dest_dir is None:
        console.print(
            "  [yellow]⚠  iCloud Books copy skipped — library folder not found.[/yellow]\n"
            "  [dim]Enable iCloud for Books on this Mac, or set icloud_books_dir in the dashboard.[/dim]"
        )
        return False

    dest_path = dest_dir / epub_path.name
    try:
        shutil.copy2(epub_path, dest_path)
        console.print(
            f"  [green]✓[/green]  Copied to iCloud Books: [dim]{dest_path.name}[/dim]"
        )
        return True
    except OSError as e:
        console.print(f"  [red]✗  iCloud Books copy failed:[/red] {e}")
        return False
