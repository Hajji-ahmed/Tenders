"""Recherche interne (Module 18) : `GET /search?q=&kinds=&semantic=` — résultats groupés par nature,
chacun avec l'adresse de la page où l'ouvrir."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import deps
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import ValidationError
from app.services.internal_search import DEFAULT_LIMIT, InternalSearch, SearchResults, parse_kinds

router = APIRouter(tags=["search"], dependencies=[Depends(get_current_user)])


@router.get("/search", response_model=SearchResults)
def search(
    q: str = Query(..., min_length=1, max_length=200, description="Texte recherché"),
    kinds: str | None = Query(
        None, description="Natures séparées par des virgules : tenders, documents, projects, experts…"
    ),
    semantic: bool = Query(
        False, description="Ajouter la recherche par le sens (morceaux indexés, fiches proches)"
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=50, description="Résultats par nature"),
    db: Session = Depends(get_db),
):
    if not q.strip():
        raise ValidationError("Texte recherché vide", code="empty_query")
    try:
        wanted = parse_kinds(kinds)
    except ValueError as e:
        raise ValidationError(str(e), code="unknown_kind") from e
    embeddings = deps.get_embeddings() if semantic else None
    return InternalSearch(db, embeddings).run(q, kinds=wanted, semantic=semantic, limit=limit)
