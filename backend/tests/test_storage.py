import uuid
from pathlib import Path

import pytest

from app.config import Settings
from app.services.storage import (
    UploadValidationError,
    content_hash,
    store_upload,
)


@pytest.fixture
def patched_storage(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "app.services.storage.get_settings",
        lambda: Settings(storage_dir=str(tmp_path)),
    )
    return tmp_path


def test_stored_name_is_unpredictable_and_safe(patched_storage: Path) -> None:
    kb_id = uuid.uuid4()
    stored = store_upload(
        kb_id=kb_id,
        original_filename="../../../etc/passwd.md",
        data="# 安全\n正文".encode(),
        max_upload_size_bytes=1024 * 1024,
    )

    assert stored.original_filename == "passwd.md"
    assert ".." not in stored.storage_key
    assert "/" not in stored.stored_name
    assert stored.stored_name.endswith(".md")

    on_disk = patched_storage / str(kb_id) / stored.stored_name
    assert on_disk.exists()
    assert str(patched_storage) in str(on_disk.resolve())


def test_store_computes_sha256_and_rejects_empty_file(patched_storage: Path) -> None:
    data = b"hello"
    stored = store_upload(
        kb_id=uuid.uuid4(),
        original_filename="a.md",
        data=data,
        max_upload_size_bytes=1024,
    )
    assert stored.content_hash == content_hash(data)

    with pytest.raises(UploadValidationError):
        store_upload(
            kb_id=uuid.uuid4(),
            original_filename="empty.md",
            data=b"",
            max_upload_size_bytes=1024,
        )


def test_unsupported_extension_rejected(patched_storage: Path) -> None:
    with pytest.raises(UploadValidationError):
        store_upload(
            kb_id=uuid.uuid4(),
            original_filename="malware.exe",
            data=b"MZ",
            max_upload_size_bytes=1024,
        )
