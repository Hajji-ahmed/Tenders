"""Vecteurs sémantiques (`EmbeddingProvider`) : OpenAI text-embedding-3-small (1536 dims) en réel,
`FakeEmbeddings` déterministe en test. Utilisés par la déduplication (RB-001) puis la recherche
interne (Phase 6)."""

import hashlib
import math
import time
from typing import Any, Protocol

import openai
import structlog
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings

log = structlog.get_logger(__name__)

BATCH_SIZE = 100  # textes par appel API
RETRYABLE = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


class EmbeddingProvider(Protocol):
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddings:
    """Vecteur unitaire déterministe dérivé du hash du texte : deux textes identiques → même vecteur,
    deux textes différents → vecteurs différents (quasi orthogonaux). Aucun réseau."""

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend(b / 255.0 - 0.5 for b in digest)
            counter += 1
        values = values[: self.dimensions]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class _OpenAILike(Protocol):
    embeddings: Any


class OpenAIEmbeddings:
    def __init__(
        self,
        settings: Settings,
        *,
        client: _OpenAILike | None = None,
        retries: int = 3,
        retry_wait: float = 1.0,
    ):
        self._client = client or openai.OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.dimensions = settings.embedding_dimensions
        self.retries = retries
        self.retry_wait = retry_wait

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._batch(texts[start : start + BATCH_SIZE]))
        return vectors

    def _batch(self, batch: list[str]) -> list[list[float]]:
        started = time.perf_counter()
        retryer = Retrying(
            stop=stop_after_attempt(self.retries),
            wait=wait_exponential(multiplier=self.retry_wait, max=30),
            retry=retry_if_exception_type(RETRYABLE),
            reraise=True,
        )
        response = retryer(
            self._client.embeddings.create, model=self.model, input=batch, dimensions=self.dimensions
        )
        usage = getattr(response, "usage", None)
        log.info(
            "embeddings.call",
            model=self.model,
            count=len(batch),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        ordered = sorted(response.data, key=lambda item: item.index)  # l'ordre d'entrée fait foi
        return [list(item.embedding) for item in ordered]
