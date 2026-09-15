from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from app.ai.llm import LLMError
from app.ai.openai_llm import OpenAILLM
from app.core.config import Settings


class Answer(BaseModel):
    value: int


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        secret_key="x" * 40,
        openai_api_key="sk-test",
        openai_model_fast="gpt-fast",
        openai_model_strong="gpt-strong",
    )


def _completion(parsed=None, content=None, refusal=None):
    message = SimpleNamespace(parsed=parsed, content=content, refusal=refusal)
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model="gpt-fast-2026")


class _FakeOpenAI:
    """Client OpenAI simulé : `chat.completions.parse` / `.create` scriptés (réponses ou exceptions)."""

    def __init__(self, parse_script: list, create_script: list | None = None):
        self.parse_calls: list[dict] = []
        self.create_calls: list[dict] = []
        outer = self

        class _Completions:
            def parse(self, **kw):
                outer.parse_calls.append(kw)
                item = parse_script.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

            def create(self, **kw):
                outer.create_calls.append(kw)
                item = (create_script or []).pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        self.chat = SimpleNamespace(completions=_Completions())


def _rate_limit() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)


def test_structured_sends_messages_and_schema_and_picks_model_by_tier():
    client = _FakeOpenAI([_completion(parsed=Answer(value=7)), _completion(parsed=Answer(value=8))])
    llm = OpenAILLM(_settings(), client=client, retry_wait=0)

    assert llm.structured(system="SYS", user="USER", output=Answer).value == 7
    call = client.parse_calls[0]
    assert call["model"] == "gpt-fast" and call["response_format"] is Answer and call["temperature"] == 0.0
    assert call["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]

    assert llm.structured(system="s", user="u", output=Answer, tier="strong", temperature=0.3).value == 8
    assert client.parse_calls[1]["model"] == "gpt-strong" and client.parse_calls[1]["temperature"] == 0.3


def test_structured_retries_on_rate_limit_and_connection_errors():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client = _FakeOpenAI(
        [_rate_limit(), openai.APIConnectionError(request=request), _completion(parsed=Answer(value=1))]
    )
    llm = OpenAILLM(_settings(), client=client, retry_wait=0)
    assert llm.structured(system="s", user="u", output=Answer).value == 1
    assert len(client.parse_calls) == 3


def test_structured_gives_up_after_three_attempts():
    client = _FakeOpenAI([_rate_limit(), _rate_limit(), _rate_limit(), _rate_limit()])
    llm = OpenAILLM(_settings(), client=client, retry_wait=0)
    with pytest.raises(openai.RateLimitError):
        llm.structured(system="s", user="u", output=Answer)
    assert len(client.parse_calls) == 3


def test_refusal_or_missing_parse_raises_llm_error_without_retry():
    client = _FakeOpenAI([_completion(parsed=None, refusal="Je ne peux pas.")])
    llm = OpenAILLM(_settings(), client=client, retry_wait=0)
    with pytest.raises(LLMError, match="Je ne peux pas"):
        llm.structured(system="s", user="u", output=Answer)
    assert len(client.parse_calls) == 1


def test_text_uses_plain_completion():
    client = _FakeOpenAI([], create_script=[_completion(content="  Résumé.  ")])
    llm = OpenAILLM(_settings(), client=client, retry_wait=0)
    assert llm.text(system="s", user="u", tier="strong") == "Résumé."
    assert client.create_calls[0]["model"] == "gpt-strong" and client.create_calls[0]["temperature"] == 0.2
