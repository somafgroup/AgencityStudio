import pytest

from common.storage import LocalStorage


def test_local_storage_saves_nested_file_inside_root(tmp_path):
    storage = LocalStorage(str(tmp_path))

    saved = storage.save("exports/result.txt", b"agencity")

    assert (tmp_path / "exports" / "result.txt").read_bytes() == b"agencity"
    assert saved == str((tmp_path / "exports" / "result.txt").resolve())


@pytest.mark.parametrize("name", ["../outside.txt", "nested/../../outside.txt"])
def test_local_storage_rejects_parent_traversal(tmp_path, name):
    storage = LocalStorage(str(tmp_path))

    with pytest.raises(ValueError, match="storage root"):
        storage.save(name, b"blocked")
