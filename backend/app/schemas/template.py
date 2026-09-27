"""Schémas des modèles de documents. La validation porte sur ce qui rend un plan **utilisable par la
génération** : des clés de section uniques, des sources connues, une longueur bornée."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.models import DocumentType, SectionSource

MAX_WORDS_RANGE = (50, 2000)
REPEAT_TARGETS = ("experts", "projects")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)]


class SectionSpec(BaseModel):
    key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    instructions: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    max_words: int = Field(ge=MAX_WORDS_RANGE[0], le=MAX_WORDS_RANGE[1])
    requires: list[SectionSource] = Field(
        min_length=1, description="Sources autorisées : rien d'autre n'entrera dans le contexte"
    )


def _unique_keys(sections: list[SectionSpec]) -> list[SectionSpec]:
    keys = [s.key for s in sections]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(f"Clés de section en double (elles doivent être uniques) : {', '.join(duplicates)}")
    return sections


class TemplateIn(BaseModel):
    name: Name
    document_type: DocumentType
    description: str | None = Field(None, max_length=2000)
    sections: list[SectionSpec] = Field(min_length=1)
    language: str = Field("fr", min_length=2, max_length=8)
    repeat_for: str | None = None

    @field_validator("sections")
    @classmethod
    def check_sections(cls, sections: list[SectionSpec]) -> list[SectionSpec]:
        return _unique_keys(sections)

    @field_validator("repeat_for")
    @classmethod
    def check_repeat(cls, value: str | None) -> str | None:
        if value is not None and value not in REPEAT_TARGETS:
            raise ValueError(f"repeat_for doit valoir {' ou '.join(REPEAT_TARGETS)}")
        return value


class TemplateUpdate(BaseModel):
    name: Name | None = None
    description: str | None = Field(None, max_length=2000)
    sections: list[SectionSpec] | None = Field(None, min_length=1)
    language: str | None = Field(None, min_length=2, max_length=8)
    repeat_for: str | None = None
    is_default: bool | None = None

    _check_sections = field_validator("sections")(
        lambda cls, v: None if v is None else _unique_keys(v)  # noqa: N805
    )


class TemplateOut(BaseModel):
    id: UUID
    name: str
    document_type: DocumentType
    description: str | None
    sections: list[SectionSpec]
    language: str
    version: int
    is_default: bool
    repeat_for: str | None
    created_at: datetime
    updated_at: datetime
    # Calculé à la validation plutôt qu'en `computed_field` : mypy ne suit pas un décorateur
    # au-dessus de `@property`, et l'interface a juste besoin du nombre.
    section_count: int = 0

    @model_validator(mode="after")
    def count_sections(self) -> "TemplateOut":
        self.section_count = len(self.sections)
        return self

    model_config = {"from_attributes": True}
