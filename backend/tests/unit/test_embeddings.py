import math
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.ai.embeddings import FakeEmbeddings, OpenAIEmbeddings
from app.core import deps
from app.core.config import Settings


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def test_fake_embeddings_are_deterministic_unit_vectors():
    fake = FakeEmbeddings()
    a, b, c = fake.embed(["Refonte du SI", "Refonte du SI", "Audit énergétique"])
    assert fake.dimensions == 1536 and len(a) == 1536
    assert a == b and a != c
    assert abs(_norm(a) - 1.0) < 1e-6
    assert fake.embed([]) == []
    assert FakeEmbeddings(dimensions=8).embed(["x"])[0].__len__() == 8


class _Client:
    def __init__(self, script: list):
        self.calls: list[dict] = []
        outer = self

        class _Embeddings:
            def create(self, **kw):
                outer.calls.append(kw)
                item = script.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        self.embeddings = _Embeddings()


def _response(vectors: list[list[float]]):
    # L'API peut renvoyer les éléments dans le désordre : `index` fait foi.
    data = [SimpleNamespace(index=i, embedding=v) for i, v in enumerate(vectors)]
    return SimpleNamespace(data=list(reversed(data)), usage=SimpleNamespace(prompt_tokens=5, total_tokens=5))


def _settings() -> Settings:
    return Settings(app_env="dev", secret_key="x" * 40, openai_api_key="sk-x", embedding_dimensions=4)


def test_openai_embeddings_batches_and_keeps_input_order():
    texts = [f"t{i}" for i in range(250)]
    client = _Client(
        [_response([[1, 0, 0, 0]] * 100), _response([[0, 1, 0, 0]] * 100), _response([[0, 0, 1, 0]] * 50)]
    )
    provider = OpenAIEmbeddings(_settings(), client=client, retry_wait=0)
    vectors = provider.embed(texts)
    assert provider.dimensions == 4 and len(vectors) == 250
    assert vectors[0] == [1, 0, 0, 0] and vectors[249] == [0, 0, 1, 0]
    assert [len(c["input"]) for c in client.calls] == [100, 100, 50]
    assert client.calls[0]["model"] == "text-embedding-3-small" and client.calls[0]["dimensions"] == 4


def test_openai_embeddings_retries_on_rate_limit_and_orders_by_index():
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    err = openai.RateLimitError("slow", response=httpx.Response(429, request=request), body=None)
    client = _Client([err, _response([[1, 0, 0, 0], [0, 1, 0, 0]])])
    vectors = OpenAIEmbeddings(_settings(), client=client, retry_wait=0).embed(["a", "b"])
    assert vectors == [[1, 0, 0, 0], [0, 1, 0, 0]] and len(client.calls) == 2


def test_deps_serve_fake_embeddings_in_test_and_openai_with_key(monkeypatch):
    assert isinstance(deps.get_embeddings(), FakeEmbeddings)
    monkeypatch.setattr(deps, "get_settings", lambda: _settings())
    deps._default_embeddings.cache_clear()
    try:
        assert isinstance(deps.get_embeddings(), OpenAIEmbeddings)
    finally:
        deps._default_embeddings.cache_clear()
    monkeypatch.setattr(
        deps, "get_settings", lambda: Settings(app_env="dev", secret_key="x" * 40, openai_api_key="")
    )
    deps._default_embeddings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            deps.get_embeddings()
    finally:
        deps._default_embeddings.cache_clear()


def test_fake_embeddings_fixture_overrides(fake_embeddings):
    assert deps.get_embeddings() is fake_embeddings
