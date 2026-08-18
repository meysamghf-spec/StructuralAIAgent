"""Local filesystem storage adapter tests."""

from uuid import uuid4

import pytest

from app.application.exceptions import FileStorageError
from app.infrastructure.storage.local_file_storage import LocalFileStorage


def test_local_storage_store_and_retrieve(file_storage_root) -> None:
    storage = LocalFileStorage(file_storage_root)
    project_id = uuid4()
    file_id = uuid4()
    content = b"hello storage"

    path = storage.store(project_id, file_id, content, extension="txt")
    assert path == f"{project_id}/{file_id}.txt"
    assert storage.retrieve(path) == content


def test_local_storage_rejects_path_traversal(file_storage_root) -> None:
    storage = LocalFileStorage(file_storage_root)
    with pytest.raises(FileStorageError):
        storage.retrieve("../secrets.txt")
    with pytest.raises(FileStorageError):
        storage.retrieve("abc/../../outside.txt")


def test_local_storage_rejects_unsafe_extension(file_storage_root) -> None:
    storage = LocalFileStorage(file_storage_root)
    with pytest.raises(FileStorageError):
        storage.store(uuid4(), uuid4(), b"x", extension="../txt")
