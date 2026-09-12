from pathlib import PurePosixPath
from typing import Protocol


class StorageProvider(Protocol):
    """Stockage objet clé → octets. Implémentations : S3Storage (MinIO / R2), LocalStorage (tests)."""

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


def build_key(prefix: str, sha256: str, filename: str) -> str:
    """Clé déterministe : `<prefix>/<2 premiers hex>/<sha256><extension>` — un même contenu
    a toujours la même clé, ce qui déduplique naturellement le stockage."""
    ext = PurePosixPath(filename).suffix.lower()
    return f"{prefix}/{sha256[:2]}/{sha256}{ext}"
