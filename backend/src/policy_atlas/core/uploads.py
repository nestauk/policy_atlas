"""Files a user gives a task: checked, stored, and recorded (task 054 increment 5, C8).

One store and one table for every capability (owner, 2026-11-03); ``purpose``
says what a file is for (``toc_theory``: a user's own theory of change).

- **Where files live.** :class:`S3UploadStore` when ``POLICY_ATLAS_UPLOAD_BUCKET``
  names a bucket (staging and production: a private, encrypted bucket per
  environment, made by the infrastructure); otherwise :class:`LocalUploadStore`,
  a folder (``POLICY_ATLAS_UPLOAD_DIR``, default ``.uploads``) for development.
  Keys are ``tasks/<task_id>/<upload_id>``, so a task's files sit together.
- **What is accepted.** PNG, JPEG or PDF, at most 10 MB, checked by the declared
  type *and* the file's first bytes, so a renamed file is refused.
- **Who sees them.** Only the backend reads the store; a route checks the
  caller may edit the task before sending a file back.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import task_upload

BUCKET_ENV = "POLICY_ATLAS_UPLOAD_BUCKET"
DIR_ENV = "POLICY_ATLAS_UPLOAD_DIR"
MAX_BYTES = 10 * 1024 * 1024
UPLOAD_EVENT = "upload.stored"

#: Accepted types and the first bytes each must start with.
MAGIC: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "application/pdf": (b"%PDF-",),
}


class UploadRefused(ValueError):
    """A file the checks refuse; ``code`` names why."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UploadStore(Protocol):
    """Where upload bytes live."""

    def put(self, key: str, data: bytes, content_type: str) -> None:
        """Store ``data`` under ``key``."""
        ...

    def get(self, key: str) -> bytes:
        """The bytes under ``key``."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key`` (a missing key is not an error)."""
        ...


class LocalUploadStore:
    """A folder on disk, for development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError(f"key outside the store: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3UploadStore:
    """A private S3 bucket. The backend's task role gives the credentials (no keys)."""

    def __init__(self, bucket: str, client: Any | None = None) -> None:
        import boto3

        self.bucket = bucket
        self.client = client if client is not None else boto3.client("s3")

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return bytes(response["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def store_from_env() -> UploadStore:
    """S3 when a bucket is named, else the local folder."""
    bucket = os.environ.get(BUCKET_ENV)
    if bucket:
        return S3UploadStore(bucket)
    return LocalUploadStore(Path(os.environ.get(DIR_ENV, ".uploads")))


def check(data: bytes, content_type: str) -> None:
    """Refuse a file that is empty, too big, or not what it says it is.

    Raises:
        UploadRefused: ``upload_type`` or ``upload_size``.
    """
    if content_type not in MAGIC:
        raise UploadRefused("upload_type", "Upload a PNG, JPEG or PDF file.")
    if not data or len(data) > MAX_BYTES:
        raise UploadRefused("upload_size", "The file must be under 10 MB.")
    if not data.startswith(MAGIC[content_type]):
        raise UploadRefused("upload_type", "The file is not the type its name says.")


@dataclass(frozen=True)
class Upload:
    """One stored upload, as the table holds it."""

    upload_id: uuid.UUID
    task_id: uuid.UUID
    purpose: str
    object_key: str
    file_name: str
    content_type: str
    size_bytes: int


def save(
    conn: Connection,
    store: UploadStore,
    *,
    task_id: uuid.UUID,
    purpose: str,
    file_name: str,
    content_type: str,
    data: bytes,
    user_id: str,
) -> Upload:
    """Check, store and record one file, with an audit event.

    The bytes go to the store before the row is written: a failed store leaves
    no row; a failed row leaves an unreferenced object, never a row with no file.

    Raises:
        UploadRefused: As :func:`check`.
    """
    check(data, content_type)
    upload_id = uuid.uuid4()
    key = f"tasks/{task_id}/{upload_id}"
    store.put(key, data, content_type)
    name = Path(file_name).name[:200] or "upload"
    row = {
        "upload_id": upload_id,
        "task_id": task_id,
        "purpose": purpose,
        "object_key": key,
        "file_name": name,
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "uploaded_by": user_id,
        "uploaded_at": datetime.now(UTC),
    }
    conn.execute(task_upload.insert().values(**row))
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=UPLOAD_EVENT,
        payload={
            "upload_id": str(upload_id),
            "purpose": purpose,
            "file_name": name,
            "content_type": content_type,
            "size_bytes": len(data),
            "by": user_id,
        },
    )
    return Upload(upload_id, task_id, purpose, key, name, content_type, len(data))


def find(conn: Connection, *, task_id: uuid.UUID, upload_id: uuid.UUID) -> Upload | None:
    """The task's upload, or ``None`` (an upload of another task is never found)."""
    row = conn.execute(
        select(task_upload).where(
            task_upload.c.task_id == task_id, task_upload.c.upload_id == upload_id
        )
    ).one_or_none()
    if row is None:
        return None
    return Upload(
        row.upload_id,
        row.task_id,
        row.purpose,
        row.object_key,
        row.file_name,
        row.content_type,
        row.size_bytes,
    )
