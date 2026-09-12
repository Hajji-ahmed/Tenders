import pytest

from app.connectors.storage.base import build_key
from app.connectors.storage.local import LocalStorage


def test_local_storage_roundtrip(tmp_path):
    st = LocalStorage(tmp_path)
    st.put("a/b/file.txt", b"hello", "text/plain")
    assert st.exists("a/b/file.txt")
    assert st.get("a/b/file.txt") == b"hello"
    st.delete("a/b/file.txt")
    assert not st.exists("a/b/file.txt")


def test_local_storage_refuses_path_escape(tmp_path):
    st = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        st.put("../outside.txt", b"x", "text/plain")


def test_build_key():
    assert build_key("company", "abcdef0123", "Dossier.PDF") == "company/ab/abcdef0123.pdf"
    assert build_key("tenders/42", "ff00", "sans-extension") == "tenders/42/ff/ff00"


def test_storage_fixture_is_local(storage, tmp_path):
    assert isinstance(storage, LocalStorage)
