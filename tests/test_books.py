from pathlib import Path

import books
from settings_store import Settings


def test_resolve_icloud_books_dir_uses_override(tmp_path):
    settings = Settings(icloud_books_dir=str(tmp_path))
    assert books.resolve_icloud_books_dir(settings) == tmp_path


def test_resolve_icloud_books_dir_missing_override_returns_none(tmp_path):
    missing = tmp_path / "missing"
    settings = Settings(icloud_books_dir=str(missing))
    assert books.resolve_icloud_books_dir(settings) is None


def test_copy_to_icloud_books(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    epub = tmp_path / "digest.epub"
    epub.write_bytes(b"epub")

    settings = Settings(icloud_books_dir=str(library))
    assert books.copy_to_icloud_books(epub, settings) is True
    assert (library / "digest.epub").read_bytes() == b"epub"


def test_copy_to_icloud_books_skips_missing_file(tmp_path, capsys):
    settings = Settings(icloud_books_dir=str(tmp_path))
    assert books.copy_to_icloud_books(tmp_path / "missing.epub", settings) is False
