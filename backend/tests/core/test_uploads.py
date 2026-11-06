"""Uploads: the checks, the local folder, and S3 against botocore's fake (task 054, C8)."""

from __future__ import annotations

import io
from pathlib import Path

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from policy_atlas.core import uploads
from policy_atlas.core.uploads import (
    LocalUploadStore,
    S3UploadStore,
    UploadRefused,
    check,
    store_from_env,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"\x00" * 32


def test_a_file_is_checked_by_its_type_and_its_first_bytes() -> None:
    check(PNG, "image/png")
    check(PDF, "application/pdf")
    check(b"\xff\xd8\xff\xe0" + b"\x00" * 8, "image/jpeg")
    # A PDF renamed to .png, an unknown type, an empty file, a file over 10 MB.
    for data, kind, code in (
        (PDF, "image/png", "upload_type"),
        (PNG, "image/gif", "upload_type"),
        (b"", "image/png", "upload_size"),
        (PNG + b"\x00" * uploads.MAX_BYTES, "image/png", "upload_size"),
    ):
        with pytest.raises(UploadRefused) as refused:
            check(data, kind)
        assert refused.value.code == code


def test_the_local_store_keeps_files_under_its_folder(tmp_path: Path) -> None:
    store = LocalUploadStore(tmp_path)
    store.put("tasks/t/u", PNG, "image/png")
    assert store.get("tasks/t/u") == PNG
    with pytest.raises(ValueError, match="outside the store"):
        store.put("../escape", PNG, "image/png")


def test_the_s3_store_puts_encrypted_and_gets() -> None:
    client = boto3.client(
        "s3", region_name="eu-west-2", aws_access_key_id="x", aws_secret_access_key="x"
    )
    with Stubber(client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "uploads",
                "Key": "tasks/t/u",
                "Body": PNG,
                "ContentType": "image/png",
                "ServerSideEncryption": "AES256",
            },
        )
        stub.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(PNG), len(PNG))},
            {"Bucket": "uploads", "Key": "tasks/t/u"},
        )
        store = S3UploadStore("uploads", client=client)
        store.put("tasks/t/u", PNG, "image/png")
        assert store.get("tasks/t/u") == PNG
        stub.assert_no_pending_responses()


def test_the_store_is_s3_only_when_a_bucket_is_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(uploads.BUCKET_ENV, raising=False)
    monkeypatch.setenv(uploads.DIR_ENV, str(tmp_path))
    local = store_from_env()
    assert isinstance(local, LocalUploadStore) and local.root == tmp_path
    monkeypatch.setenv(uploads.BUCKET_ENV, "policy-atlas-v3-staging-uploads")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    remote = store_from_env()
    assert isinstance(remote, S3UploadStore) and remote.bucket == "policy-atlas-v3-staging-uploads"
