"""Profils de recherche : CRUD paginé (pas de rattachement à l'entreprise — un seul locataire)."""

from app.api.crud_router import build_crud_router
from app.models import SearchProfile
from app.schemas.tender import SearchProfileIn, SearchProfileOut, SearchProfileUpdate

router = build_crud_router(
    SearchProfile,
    SearchProfileIn,
    SearchProfileUpdate,
    SearchProfileOut,
    prefix="/search-profiles",
    tag="search-profiles",
    order_by=SearchProfile.name,
    scoped_to_company=False,
    audit_action="search_profile.updated",
)
