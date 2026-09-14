"""Fournisseur LLM OpenAI (`LLMProvider`) : sorties structurées via `chat.completions.parse`
(schéma Pydantic), texte via `chat.completions.create`. Deux niveaux : `fast` (extraction, scoring,
questions) et `strong` (génération). 3 tentatives avec backoff sur quota/réseau ; chaque appel
journalise modèle, jetons et durée (jamais le contenu)."""

import time
from typing import Any, Protocol

import openai
import structlog
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ai.llm import LLMError, T, Tier
from app.core.config import Settings

log = structlog.get_logger(__name__)

RETRYABLE = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


class _OpenAILike(Protocol):
    chat: Any


class OpenAILLM:
    def __init__(
        self,
        settings: Settings,
        *,
        client: _OpenAILike | None = None,
        retries: int = 3,
        retry_wait: float = 1.0,
    ):
        self._client = client or openai.OpenAI(api_key=settings.openai_api_key)
        self._models: dict[Tier, str] = {
            "fast": settings.openai_model_fast,
            "strong": settings.openai_model_strong,
        }
        self.retries = retries
        self.retry_wait = retry_wait

    def _retrying(self) -> Retrying:
        return Retrying(
            stop=stop_after_attempt(self.retries),
            wait=wait_exponential(multiplier=self.retry_wait, max=30),
            retry=retry_if_exception_type(RETRYABLE),
            reraise=True,
        )

    def _log(self, kind: str, tier: Tier, completion: Any, started: float) -> None:
        usage = getattr(completion, "usage", None)
        log.info(
            "llm.call",
            kind=kind,
            tier=tier,
            model=getattr(completion, "model", self._models[tier]),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            duration_ms=round((time.perf_counter() - started) * 1000),
        )

    def structured(
        self, *, system: str, user: str, output: type[T], tier: Tier = "fast", temperature: float = 0.0
    ) -> T:
        started = time.perf_counter()
        completion = self._retrying()(
            self._client.chat.completions.parse,
            model=self._models[tier],
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=output,
            temperature=temperature,
        )
        self._log("structured", tier, completion, started)
        message = completion.choices[0].message
        if getattr(message, "parsed", None) is None:
            raise LLMError(
                f"Sortie structurée absente ({output.__name__}) : {message.refusal or 'réponse vide'}"
            )
        return message.parsed

    def text(self, *, system: str, user: str, tier: Tier = "fast", temperature: float = 0.2) -> str:
        started = time.perf_counter()
        completion = self._retrying()(
            self._client.chat.completions.create,
            model=self._models[tier],
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
        )
        self._log("text", tier, completion, started)
        content = completion.choices[0].message.content
        if not content:
            raise LLMError("Réponse texte vide")
        return content.strip()
