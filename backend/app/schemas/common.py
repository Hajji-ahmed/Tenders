from pydantic import BaseModel


class Page[T](BaseModel):
    """Enveloppe des listes paginées (section 5 du plan) : {"items", "total", "page", "size"}."""

    items: list[T]
    total: int
    page: int
    size: int
