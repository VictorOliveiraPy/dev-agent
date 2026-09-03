"""Supervisor: decide qual especialista do time age em cada rodada.

Diferente dos Passos 2 e 3 (onde a escolha de qual agente chamar era manual,
no código Python), aqui quem decide é o próprio LLM, através de um
roteador com saída estruturada (ver Structured Output). O supervisor não
escreve código — ele só orquestra: lê o pedido original + o que já foi
feito, decide o PRÓXIMO especialista a agir (ou que o trabalho terminou),
aciona esse especialista, registra o resultado, e repete. É o núcleo de um
sistema multi-agente: um "gerente" que delega, sem conhecer os detalhes de
implementação de cada área.
"""

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agentes.equipe import criar_agente, criar_agente_com_ferramentas
from agentes.llm import build_chat_model
from agentes.tools import list_dir, read_file, run_command, write_file

TOOLS_PADRAO = [write_file, read_file, list_dir, run_command]

# Só quem produz artefatos (código) precisa de tools; o arquiteto só opina.
PAPEIS_COM_FERRAMENTAS = {"dev_backend", "dev_frontend"}

MAX_RODADAS = 6


class Decisao(BaseModel):
    """Decisão do supervisor sobre o próximo passo do time."""

    proximo: Literal["arquiteto", "dev_backend", "dev_frontend", "concluido"] = Field(
        description="Qual papel deve agir agora, ou 'concluido' se o pedido já foi atendido."
    )
    instrucao: str = Field(
        description=(
            "Instrução específica e objetiva para esse papel executar agora "
            "(ignorado se proximo == 'concluido')."
        )
    )
    justificativa: str = Field(description="Por que essa é a próxima ação certa, em 1 frase.")


_ROTEADOR_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Você é o Tech Lead que orquestra um time (arquiteto, dev_backend, "
        "dev_frontend). Dado o pedido original e o histórico do que já foi "
        "feito, decida a PRÓXIMA ação. Regra geral: o arquiteto decide a "
        "forma antes do backend implementar, e o backend expõe a API antes "
        "do frontend consumi-la — mas pule etapas óbvias se o histórico "
        "mostrar que já foram cobertas. Só retorne 'concluido' quando o "
        "pedido estiver de fato IMPLEMENTADO (código escrito de verdade), "
        "nunca apenas planejado ou parcialmente feito.",
    ),
    (
        "human",
        "PEDIDO ORIGINAL:\n{pedido}\n\nHISTÓRICO DO QUE JÁ FOI FEITO:\n{historico}",
    ),
])

# O roteador usa saída estruturada (Aula 03 do projeto de estudo) para que
# o "próximo passo" seja um objeto validado, não texto livre pra fazer
# parsing na mão.
_roteador = _ROTEADOR_PROMPT | build_chat_model(max_tokens=2048).with_structured_output(Decisao)


def executar(pedido: str) -> list[str]:
    """Roda o loop supervisor -> especialista até o pedido ser concluído.

    Args:
        pedido: descrição do que o time deve entregar.

    Returns:
        O histórico de ações executadas (uma entrada por rodada), na ordem
        em que aconteceram.
    """
    historico: list[str] = []

    for rodada in range(1, MAX_RODADAS + 1):
        texto_historico = "\n".join(historico) if historico else "(nada feito ainda)"
        decisao = _roteador.invoke({"pedido": pedido, "historico": texto_historico})

        print(f"\n--- Rodada {rodada}: supervisor escolheu '{decisao.proximo}' ---")
        print(f"Justificativa: {decisao.justificativa}")

        if decisao.proximo == "concluido":
            historico.append("[supervisor] Deu o pedido como concluído.")
            break

        if decisao.proximo in PAPEIS_COM_FERRAMENTAS:
            agente = criar_agente_com_ferramentas(decisao.proximo, TOOLS_PADRAO)
            resultado = agente.invoke({"pedido": decisao.instrucao})
            saida = resultado["output"]
            if isinstance(saida, list):
                saida = "".join(b.get("text", "") for b in saida if b.get("type") == "text")
        else:
            agente = criar_agente(decisao.proximo)
            saida = agente.invoke({"pedido": decisao.instrucao})

        resumo = f"[{decisao.proximo}] instrução: {decisao.instrucao}\nresultado: {saida[:500]}"
        historico.append(resumo)
    else:
        historico.append(f"[supervisor] Parou por atingir o limite de {MAX_RODADAS} rodadas.")

    return historico
