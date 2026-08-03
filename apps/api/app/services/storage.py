"""Object storage for uploaded resumes.

Local filesystem for now, behind an interface narrow enough that S3 or GCS
slots in without touching callers. The only operations are put, get and
delete, and `delete` really unlinks - a resume is somebody's employment
history, address and phone number, and "deleted" meaning "flagged as hidden"
is not a promise this product gets to make loosely.

Keys are scoped by user id so a path traversal in a filename cannot reach
another user's directory, and the stored name is generated rather than taken
from the upload.
"""

from __future__ import annotations

import uuid
from pathlib import Path


class StorageError(Exception):
    pass


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        # Belt and braces: keys are generated, but a bug that let one be
        # attacker-influenced should not become arbitrary file access.
        if not path.is_relative_to(self.root):
            raise StorageError("refusing a key that escapes the storage root")
        return path

    def key_for(self, user_id: uuid.UUID, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in (".pdf", ".docx"):
            suffix = ""
        return f"{user_id}/{uuid.uuid4().hex}{suffix}"

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError(f"no object at {key}") from exc

    def delete(self, key: str) -> bool:
        """Unlink the object. True if something was there."""
        path = self._path(key)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            # Already gone is the desired end state, not an error.
            return False

    def delete_prefix(self, prefix: str) -> int:
        """Remove everything under a prefix - used by "delete my data"."""
        base = self._path(prefix)
        if not base.exists():
            return 0
        removed = 0
        for path in sorted(base.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
                removed += 1
            elif path.is_dir():
                path.rmdir()
        base.rmdir()
        return removed
