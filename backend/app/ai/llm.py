"""Contrat des modèles de langage : sorties structurées (Pydantic) et texte libre, deux niveaux
(`fast` : extraction, scoring, questions ; `strong` : génération). Implémentation réelle en 3.4,
`FakeLLM` scripté pour les tests — aucun test n'appelle un fournisseur externe."""

from collections.abc import Callable
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
Tier = Literal["fast", "strong"]


class LLMError(RuntimeError):
    """Le modèle n'a pas rendu la sortie attendue (refus, réponse vide) — non réessayé."""


class LLMProvider(Protocol):
    def structured(
        self, *, system: str, user: str, output: type[T], tier: Tier = "fast", temperature: float = 0.0
    ) -> T: ...

    def text(self, *, system: str, user: str, tier: Tier = "fast", temperature: float = 0.2) -> str: ...


StructuredScript = list[BaseModel] | Callable[[str, type[BaseModel]], BaseModel]


class FakeLLM:
    """Réponses scriptées, servies dans l'ordre (liste) ou calculées (callable `(user, output) -> BaseModel`).
    Chaque appel est journalisé dans `calls` : {"system", "user", "output", "tier"}."""

    def __init__(
        self, structured_responses: StructuredScript | None = None, text_responses: list[str] | None = None
    ):
        self._structured = structured_responses if structured_responses is not None else []
        self._texts = list(text_responses or [])
        self.calls: list[dict] = []

    def structured(
        self, *, system: str, user: str, output: type[T], tier: Tier = "fast", temperature: float = 0.0
    ) -> T:
        self.calls.append({"system": system, "user": user, "output": output, "tier": tier})
        if callable(self._structured):
            return self._structured(user, output)  # type: ignore[return-value]
        if not self._structured:
            raise RuntimeError(
                f"FakeLLM : plus aucune réponse structurée scriptée (attendu : {output.__name__})"
            )
        return self._structured.pop(0)  # type: ignore[return-value]

    def text(self, *, system: str, user: str, tier: Tier = "fast", temperature: float = 0.2) -> str:
        self.calls.append({"system": system, "user": user, "output": str, "tier": tier})
        if not self._texts:
            raise RuntimeError("FakeLLM : plus aucune réponse texte scriptée")
        return self._texts.pop(0)
