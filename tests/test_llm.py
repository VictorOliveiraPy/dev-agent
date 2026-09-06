"""Testes para a fábrica de modelo (agents/llm.py).

Só cobre a lógica de seleção de provedor (anthropic vs. ollama vs.
openrouter) — nenhum destes testes chama uma API real nem precisa de um
Ollama rodando.
"""

import pytest

from agents import llm


class _FakeChatAnthropic:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeChatOllama:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture(autouse=True)
def fake_chat_models(monkeypatch):
    """Substitui os construtores reais por fakes que só gravam os kwargs."""
    monkeypatch.setattr(llm, "ChatAnthropic", _FakeChatAnthropic)
    monkeypatch.setattr(llm, "ChatOllama", _FakeChatOllama)
    monkeypatch.setattr(llm, "ChatOpenAI", _FakeChatOpenAI)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Garante que LLM_PROVIDER/OLLAMA_*/OPENROUTER_* do .env real não
    vazem pro teste."""
    for var in (
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_BASE_URL",
        "ANTHROPIC_WORKSPACE_ID",
    ):
        monkeypatch.delenv(var, raising=False)


def test_default_provider_is_anthropic():
    model = llm.build_chat_model()
    assert isinstance(model, _FakeChatAnthropic)
    assert model.kwargs["model"] == llm._DEFAULT_ANTHROPIC_MODEL
    assert model.kwargs["max_tokens"] == 8192


def test_env_var_switches_to_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    model = llm.build_chat_model()
    assert isinstance(model, _FakeChatOllama)
    assert model.kwargs["model"] == llm._DEFAULT_OLLAMA_MODEL
    assert model.kwargs["base_url"] == "http://localhost:11434"
    assert model.kwargs["num_predict"] == 8192


def test_explicit_provider_overrides_env(monkeypatch):
    """Um chamador que fixa provider="anthropic" (ex.: agents/researcher.py,
    que depende de web_search server-side) não pode ser desviado por um
    LLM_PROVIDER=ollama global.
    """
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    model = llm.build_chat_model(provider="anthropic")
    assert isinstance(model, _FakeChatAnthropic)


def test_ollama_reads_base_url_and_model_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    model = llm.build_chat_model(provider="ollama")
    assert model.kwargs["base_url"] == "http://ollama:11434"
    assert model.kwargs["model"] == "mistral"


def test_explicit_model_overrides_default():
    model = llm.build_chat_model(provider="ollama", model="qwen2.5")
    assert model.kwargs["model"] == "qwen2.5"


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="desconhecido"):
        llm.build_chat_model(provider="bedrock")


def test_env_var_switches_to_openrouter(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake")
    model = llm.build_chat_model()
    assert isinstance(model, _FakeChatOpenAI)
    assert model.kwargs["model"] == llm._DEFAULT_OPENROUTER_MODEL
    assert model.kwargs["api_key"] == "sk-or-fake"
    assert model.kwargs["base_url"] == llm._OPENROUTER_BASE_URL
    assert model.kwargs["max_completion_tokens"] == 8192


def test_openrouter_reads_model_and_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://custom.example/api/v1")
    model = llm.build_chat_model(provider="openrouter")
    assert model.kwargs["model"] == "mistralai/mistral-7b-instruct:free"
    assert model.kwargs["base_url"] == "https://custom.example/api/v1"


def test_explicit_provider_openrouter_overrides_env(monkeypatch):
    """Mesma garantia que já vale para provider="anthropic" (ver
    test_explicit_provider_overrides_env): um chamador que fixa
    provider="openrouter" não é desviado por um LLM_PROVIDER diferente.
    """
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    model = llm.build_chat_model(provider="openrouter")
    assert isinstance(model, _FakeChatOpenAI)
