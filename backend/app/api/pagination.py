from fastapi import Query
from pydantic import BaseModel


class PageParams(BaseModel):
    page: int = 1
    size: int = 50

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=100)) -> PageParams:
    """Dépendance commune à toutes les listes : `?page=1&size=50` (size plafonné à 100)."""
    return PageParams(page=page, size=size)
