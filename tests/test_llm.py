"""Testes para a fábrica de modelo (agents/llm.py).

Só cobre a lógica pura de montagem/seleção de provedor (modelo default vs.
explícito, header de workspace da Anthropic, chave da DeepSeek, resolução
de LLM_PROVIDER) — nenhum destes testes chama a API real.
"""

import pytest

from agents import llm


class _FakeChatAnthropic:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeChatDeepSeek:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture(autouse=True)
def fake_chat_models(monkeypatch):
    """Substitui os construtores reais por fakes que só gravam os kwargs."""
    monkeypatch.setattr(llm, "ChatAnthropic", _FakeChatAnthropic)
    monkeypatch.setattr(llm, "ChatDeepSeek", _FakeChatDeepSeek)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Garante que nada do .env real (workspace, provider, chave) vaza pro teste."""
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def test_should_default_to_anthropic_when_llm_provider_is_not_set():
    assert llm.current_provider() == "anthropic"


def test_should_read_llm_provider_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    assert llm.current_provider() == "deepseek"


def test_should_use_default_anthropic_model_when_none_is_given():
    model = llm.build_chat_model()
    assert isinstance(model, _FakeChatAnthropic)
    assert model.kwargs["model"] == llm._DEFAULT_MODELS["anthropic"]
    assert model.kwargs["max_tokens"] == 8192


def test_should_use_explicit_model_when_given():
    model = llm.build_chat_model(model="claude-haiku-4-5")
    assert model.kwargs["model"] == "claude-haiku-4-5"


def test_should_omit_workspace_header_when_env_var_is_not_set():
    model = llm.build_chat_model()
    assert model.kwargs["default_headers"] is None


def test_should_send_workspace_header_when_env_var_is_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "ws-123")
    model = llm.build_chat_model()
    assert model.kwargs["default_headers"] == {"anthropic-workspace-id": "ws-123"}


def test_should_build_deepseek_when_llm_provider_env_is_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    model = llm.build_chat_model()

    assert isinstance(model, _FakeChatDeepSeek)
    assert model.kwargs["model"] == llm._DEFAULT_MODELS["deepseek"]
    assert model.kwargs["api_key"] == "sk-test"
    assert model.kwargs["max_tokens"] == 8192


def test_should_build_deepseek_when_provider_arg_overrides_env(monkeypatch):
    """provider= explícito vence LLM_PROVIDER — é o que agents/researcher.py
    faz ao contrário (força 'anthropic' mesmo com LLM_PROVIDER=deepseek)."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    model = llm.build_chat_model(provider="deepseek")

    assert isinstance(model, _FakeChatDeepSeek)


def test_should_force_anthropic_when_provider_arg_overrides_deepseek_env(monkeypatch):
    """O caso real de agents/researcher.py: LLM_PROVIDER=deepseek globalmente,
    mas este papel específico força Anthropic (web_search não tem equivalente)."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")

    model = llm.build_chat_model(provider="anthropic")

    assert isinstance(model, _FakeChatAnthropic)


def test_should_raise_when_provider_is_unknown():
    with pytest.raises(ValueError, match="anthropic.*deepseek"):
        llm.build_chat_model(provider="ollama")
