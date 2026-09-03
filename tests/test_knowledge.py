"""Testes para a busca sob demanda nos padrões do time (agents/knowledge.py).

Só cobre lógica pura e determinística (BM25 é matemática, não LLM) —
nenhum destes testes chama a API da Anthropic.
"""

from agents.knowledge import StandardsIndex, _tokenize, search_standards


def test_should_tokenize_by_lowercasing_and_splitting_on_whitespace():
    """Tokenização é só minúsculas + split — sem stemming, de propósito."""
    assert _tokenize("Valide o JWT com cuidado") == ["valide", "o", "jwt", "com", "cuidado"]


def test_should_return_empty_list_when_standards_dir_has_no_markdown_files(tmp_path):
    """Uma pasta de padrões vazia não derruba a busca, só devolve nada."""
    index = StandardsIndex(standards_dir=tmp_path)

    assert index.search("qualquer coisa") == []


def test_should_rank_relevant_chunk_first_when_query_matches_its_vocabulary(tmp_path):
    """O chunk que compartilha vocabulário com a query aparece primeiro.

    Usa 3 documentos, não 2: com só 2 e um termo presente em exatamente um
    deles, a fórmula clássica de IDF do BM25 zera (log(1) = 0) — o termo
    aparece em exatamente 50% do corpus. É uma degenerescência real de
    corpus pequeno, não um bug — o teste evita cair nela mantendo o
    cenário longe da fronteira dos 50%.
    """
    (tmp_path / "backend.md").write_text(
        "# Backend\n\nSempre valide exp, iat e sub do JWT antes de aceitar o token.",
        encoding="utf-8",
    )
    (tmp_path / "design.md").write_text(
        "# Design\n\nEvite rounded-lg em tudo, gaste borda e sombra por papel.",
        encoding="utf-8",
    )
    (tmp_path / "general.md").write_text(
        "# Geral\n\nDocstrings e comentários ficam em português no código.",
        encoding="utf-8",
    )
    index = StandardsIndex(standards_dir=tmp_path)

    results = index.search("como validar o token JWT")

    assert results
    assert results[0].source == "backend.md"


def test_should_return_no_relevant_chunk_message_when_search_standards_finds_nothing(monkeypatch):
    """A tool devolve uma mensagem clara, não uma lista vazia ou erro, quando não acha nada."""
    from agents import knowledge

    monkeypatch.setattr(knowledge._index, "search", lambda query, k=3: [])

    result = search_standards.invoke({"query": "algo que não existe em nenhum padrão"})

    assert "Nenhum trecho relevante" in result


def test_should_format_chunks_with_source_label_when_search_standards_finds_matches(monkeypatch):
    """A tool identifica de qual arquivo cada trecho veio, pro agente saber a origem."""
    from agents import knowledge

    fake_chunk = knowledge.Chunk(source="backend.md", text="Valide o JWT.")
    monkeypatch.setattr(knowledge._index, "search", lambda query, k=3: [fake_chunk])

    result = search_standards.invoke({"query": "jwt"})

    assert "[backend.md]" in result
    assert "Valide o JWT." in result
