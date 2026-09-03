"""Busca sob demanda nos padrões do time (`standards/*.md`), via BM25.

Por que BM25 (busca por palavra-chave) em vez de embeddings semânticos —
decisão registrada em ARCHITECTURE.md, seção "RAG sobre standards/*.md":
nosso corpus é pequeno (poucos arquivos `.md`) e usa vocabulário técnico
bem específico ("IDOR", "JWT", "hex", "rounded-lg") — BM25 lida bem com
isso sem precisar baixar um modelo de embeddings (~100-800MB com PyTorch)
nem gastar chamada de API. Sem dependência pesada: `rank_bm25` é puro
Python, poucos KB.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

# Letras (com acentos do português) e dígitos formam um token; qualquer
# outra coisa é separador. Sem isso, pontuação de markdown gruda na
# palavra ("**idor" em vez de "idor", "rounded-lg." em vez de "rounded" +
# "lg") e a busca por palavra-chave erra o alvo — bug real encontrado ao
# testar contra os standards/*.md de verdade.
_TOKEN_PATTERN = re.compile(r"[a-zà-öø-ÿ0-9]+")

logger = logging.getLogger(__name__)

STANDARDS_DIR = Path(__file__).parent.parent / "standards"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class Chunk:
    """Um pedaço indexado de um arquivo de padrões."""

    source: str
    text: str


def _tokenize(text: str) -> list[str]:
    """Tokenização: minúsculas + extrai sequências de letras/dígitos.

    Não é um `.split()` por espaço — pontuação de markdown (`**`, `` ` ``,
    `#`, `-`, `.`) precisa ser tratada como separador, senão vira parte do
    token ("**idor" em vez de "idor") e a busca por palavra-chave erra o
    alvo. BM25 ainda não precisa de nada mais sofisticado que isso
    (stemming, remoção de stop words) pra um corpus pequeno e técnico como
    o nosso — ver ARCHITECTURE.md antes de complicar mais.
    """
    return _TOKEN_PATTERN.findall(text.lower())


def load_chunks(standards_dir: Path = STANDARDS_DIR) -> list[Chunk]:
    """Lê todo `standards/*.md` e quebra em pedaços menores (chunks).

    Args:
        standards_dir: diretório com os arquivos de padrões (parametrizado
            pra permitir teste com uma pasta isolada, sem tocar nos
            padrões reais do projeto).
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks: list[Chunk] = []
    for path in sorted(standards_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for piece in splitter.split_text(text):
            chunks.append(Chunk(source=path.name, text=piece))
    return chunks


class StandardsIndex:
    """Índice BM25 sobre os chunks de `standards/*.md`.

    Construído uma vez (na importação do módulo, ver `_index` no fim deste
    arquivo) e reaproveitado por toda busca — os `.md` de padrões não mudam
    durante uma execução normal do time, só entre uma run e outra.
    """

    def __init__(self, standards_dir: Path = STANDARDS_DIR) -> None:
        self.standards_dir = standards_dir
        self._chunks = load_chunks(standards_dir)
        corpus = [_tokenize(chunk.text) for chunk in self._chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        """Devolve os `k` chunks mais relevantes pra `query`.

        Chunks com score zero (nenhuma palavra em comum com a query) são
        descartados — devolver um chunk irrelevante só porque "sobrou
        espaço" no top-k seria pior que devolver menos resultados.
        """
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            zip(scores, self._chunks, strict=True), key=lambda pair: pair[0], reverse=True
        )
        return [chunk for score, chunk in ranked[:k] if score > 0]


# Instância única, construída na importação — ver docstring de StandardsIndex.
_index = StandardsIndex()


@tool
def search_standards(query: str) -> str:
    """Busca trechos relevantes dos padrões do time (standards/*.md) sob demanda.

    Use isso quando precisar de uma regra ESPECÍFICA que talvez não esteja
    resumida na sua persona, ou pra confirmar um detalhe exato (ex: "qual
    o limite de cobertura de teste?", "quais clichês de design evitar?").

    Args:
        query: a pergunta ou termo de busca, em português ou inglês.
    """
    results = _index.search(query, k=3)
    if not results:
        return "Nenhum trecho relevante encontrado nos padrões do time."
    return "\n\n---\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in results)
