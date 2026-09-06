"""Testes para a fábrica de modelo (agents/llm.py).

Só cobre a lógica pura de montagem do ChatAnthropic (modelo default vs.
explícito, header de workspace) — nenhum destes testes chama a API real.
"""

import pytest

from agents import llm


class _FakeChatAnthropic:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture(autouse=True)
def fake_chat_anthropic(monkeypatch):
    """Substitui o construtor real por um fake que só grava os kwargs."""
    monkeypatch.setattr(llm, "ChatAnthropic", _FakeChatAnthropic)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Garante que ANTHROPIC_WORKSPACE_ID do .env real não vaza pro teste."""
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)


def test_should_use_default_model_when_none_is_given():
    model = llm.build_chat_model()
    assert isinstance(model, _FakeChatAnthropic)
    assert model.kwargs["model"] == llm._DEFAULT_MODEL
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
