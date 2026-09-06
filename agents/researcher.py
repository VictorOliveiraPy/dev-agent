"""Agente pesquisador: propõe novas entradas do acervo com base em busca
web real, e valida o que ele propõe antes de qualquer coisa virar arquivo.

Diferença de desenho em relação aos outros papéis (ver `team.py`): este
módulo NÃO usa `AgentExecutor`. A busca web (`web_search`) é uma tool
*server-side* da própria Anthropic — o modelo a executa e recebe o
resultado dentro da mesma chamada, sem round-trip pelo cliente. A única
tool que este módulo precisa interceptar é `submit_entries`, a saída
final estruturada. Por isso um loop simples (chamar o modelo, checar se
ele já chamou `submit_entries`, senão insistir) é suficiente — não é
preciso o loop genérico de tool-calling do LangChain.

O ponto mais importante deste módulo não é a busca, é a validação depois
dela. O gap documentado em PROGRESS.md — "os agentes não tinham como se
autovalidar" — se aplica em cheio a conteúdo: um modelo pode dizer que
encontrou uma fonte e não ter encontrado, ou (mais comum) montar uma URL
de imagem "parecida" com uma que viu de verdade. `validate_batch` por
isso não confia em nada que o modelo afirma: valida cada item contra o
schema Pydantic REAL do backend (importado do repositório
`acervo-catolico-api`, não duplicado aqui) e faz uma requisição HTTP de
verdade em cada URL de imagem proposta, descartando a imagem (nunca a
entrada inteira) se ela não resolver como imagem de verdade.

Usa Sonnet 5 por padrão, não o Opus 5 dos demais papéis (ver
`agents/llm.py::_DEFAULT_MODEL`) — pesquisa grounded em busca depende
mais de seguir regras à risca (nunca inventar, sempre citar) do que do
raciocínio mais caro do Opus, e o custo real observado desse papel é alto
por causa do próprio `web_search` (ver PROGRESS.md), não por precisar do
modelo mais caro.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from agents.llm import build_chat_model
from agents.team import _system_message
from agents.usage import usage_handler

logger = logging.getLogger(__name__)

ROLE = "pesquisador"

# Mais barato que o Opus 5 padrão do time (agents/llm.py) — ver nota no
# docstring do módulo sobre por que este papel não precisa do modelo mais
# caro.
_DEFAULT_MODEL = "claude-sonnet-5"

# Descrição do papel — mesma convenção de agents.team.ROLES, mas vive
# aqui (não lá) porque este papel não segue o padrão create_agent /
# create_agent_with_tools dos demais. Também não inclui standards/general.md
# (via _build_persona) de propósito: aquele arquivo fala de instalar
# dependências, rodar lint/testes de CÓDIGO — não se aplica a uma tarefa
# que só produz dados JSON. As regras de autovalidação equivalentes para
# este papel estão listadas abaixo, e a validação de verdade é código
# (validate_batch), não instrução de prompt.
_PERSONA = (
    "Você é o Pesquisador de Conteúdo do time. Sua função é encontrar, "
    "usando a ferramenta de busca web disponível, fatos REAIS e "
    "verificáveis para novas entradas do Acervo Católico, e propô-las "
    "através da tool `submit_entries` — nunca inventa fato, data ou "
    "imagem.\n\n"
    "Regras inegociáveis:\n"
    "1. Toda entrada deve se apoiar em pelo menos uma busca real feita "
    "nesta conversa. Nunca preencha um campo (data, local, título "
    "honorífico) de memória sem confirmar por busca — mesmo que pareça "
    "óbvio ou amplamente sabido.\n"
    "2. Onde a data ou o fato não for claro, ou houver divergência entre "
    "fontes encontradas, prefira omitir o campo (null) ou marcá-lo como "
    "aproximado ('c. 1400', 'segundo a tradição') a inventar precisão.\n"
    "3. Para 'imagem', proponha APENAS uma URL de arquivo que você tenha "
    "efetivamente visto nos resultados de busca, no formato "
    "https://upload.wikimedia.org/wikipedia/commons/X/XX/Nome.ext — "
    "nunca componha uma URL por analogia com outra que você viu (trocar "
    "só o nome do arquivo, por exemplo). Se não tiver certeza absoluta de "
    "que a URL existe, deixe 'imagem' como null: uma etapa automática "
    "depois desta vai checar a URL de verdade e descartar qualquer "
    "imagem que não resolva — sempre prefira null a uma URL inventada.\n"
    "4. Preencha 'imagem_credito' só quando souber que a licença exige "
    "atribuição (CC BY / CC BY-SA), citando fotógrafo/autor e ano quando "
    "houver; domínio público e CC0 ficam com 'imagem_credito': null.\n"
    "5. 'fontes' deve citar a referência real usada (documento "
    "pontifício, ata conciliar, artigo específico da Wikipedia, "
    "martirológio) — nunca deixe vazio.\n"
    "6. Nunca proponha um slug que já exista no acervo — a lista de "
    "slugs já existentes na categoria vem na própria tarefa.\n"
    "7. 'tags' são palavras ou expressões naturais em português, com "
    "acento e espaço normais — nunca 'kebab-case-sem-acento'. Exemplos "
    "REAIS já usados no acervo: 'trindade', 'século V', 'Leão Magno', "
    "'Cirilo de Alexandria'. NUNCA assim: 'seculo-v', 'leao-magno', "
    "'cirilo-de-alexandria' — isso já aconteceu e quebra a busca por "
    "tema do site, que depende de tags no mesmo formato em toda entrada.\n"
    "8. Escreva 'corpo' e 'resumo' inteiramente em português — releia "
    "antes de propor a entrada e corrija qualquer palavra ou expressão "
    "que tenha escapado em inglês (já aconteceu: 'rightly' dentro de uma "
    "frase em português).\n"
    "9. Quando terminar de pesquisar todos os itens pedidos, chame a "
    "tool `submit_entries` UMA única vez, com todos os itens juntos."
)


def _web_search_tool(max_uses: int = 15) -> dict[str, Any]:
    """Tool nativa de busca web da Anthropic — resolvida no servidor.

    `max_uses` limita quantas buscas o modelo pode fazer numa única
    chamada, como teto de custo/tempo por lote — não é um limite de
    qualidade, é proteção contra um loop de busca sem necessidade.
    """
    return {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}


def _submit_entries_tool(item_schema: dict[str, Any]) -> dict[str, Any]:
    """Tool "de verdade" (client-side): a saída final e estruturada do lote.

    O schema de cada item é o `model_json_schema()` do modelo Pydantic
    real da categoria (ver `research_batch`) — a mesma fonte usada depois
    para validar, então o modelo nunca vê um contrato diferente do que
    será exigido dele.
    """
    return {
        "name": "submit_entries",
        "description": (
            "Envia o lote final de entradas pesquisadas para esta tarefa, "
            "uma por item, depois de concluída toda a pesquisa necessária."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"itens": {"type": "array", "items": item_schema}},
            "required": ["itens"],
        },
    }


def research_batch(
    task: str,
    item_model: type[BaseModel],
    *,
    max_attempts: int = 3,
    max_tokens: int = 16000,
    model: str = _DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    """Pesquisa e propõe um lote de entradas — SEM validar (ver `validate_batch`).

    Args:
        task: descrição da tarefa (ex.: "pesquise os concílios ecumênicos
            que faltam: Constantinopla I, Éfeso, ... Slugs já existentes:
            niceia-i, trento, vaticano-ii.").
        item_model: o modelo Pydantic REAL da categoria (ex.: `Concilio`,
            importado do backend) — vira tanto o schema da tool quanto,
            depois, o validador em `validate_batch`.
        max_attempts: quantas vezes insistir se o modelo responder sem
            chamar `submit_entries` (ex.: fez só uma pergunta de volta).
        model: ID do modelo Claude. Padrão é Sonnet 5, não o Opus 5 dos
            demais papéis — ver nota no docstring do módulo.
        max_tokens: teto de saída do modelo. Um lote com muitos itens
            (bug real já visto: 18 concílios numa chamada só, 200k tokens
            de entrada por causa dos resultados de busca acumulados)
            estoura esse teto e corta a resposta no meio do JSON da tool
            call — prefira lotes menores (3-6 itens) a subir este valor
            sem necessidade.

    Returns:
        A lista bruta de itens (dicts) que o modelo propôs — ainda não
        validada nem verificada. Gasta tokens de API reais a cada chamada.

    Raises:
        RuntimeError: se a resposta for cortada por `max_tokens`
            (`stop_reason == "max_tokens"`), se `submit_entries` vier sem
            o campo `itens`, ou se o modelo não chamar `submit_entries`
            depois de `max_attempts` tentativas.
    """
    tools = [_web_search_tool(), _submit_entries_tool(item_model.model_json_schema())]
    chat_model = (
        build_chat_model(max_tokens=max_tokens, model=model)
        .bind_tools(tools)
        .with_config(callbacks=[usage_handler], tags=[f"role:{ROLE}"])
    )

    messages: list[Any] = [_system_message(_PERSONA), HumanMessage(content=task)]

    for attempt in range(max_attempts):
        response = chat_model.invoke(messages)

        stop_reason = response.response_metadata.get("stop_reason")
        if stop_reason == "max_tokens":
            # Bug real já visto neste projeto (ver ARCHITECTURE.md): a
            # resposta foi cortada no meio — inclusive, possivelmente, no
            # meio do JSON da tool call. Não adianta tentar ler tool_calls
            # daqui: o pedido era grande demais para max_tokens. Falhar
            # alto e claro é melhor que um KeyError sem contexto.
            raise RuntimeError(
                "Resposta cortada por max_tokens (stop_reason=max_tokens) — "
                "o lote pedido é grande demais para uma chamada só. Peça "
                "menos itens por vez ou aumente max_tokens."
            )

        for call in response.tool_calls:
            if call["name"] == "submit_entries":
                if "itens" not in call.get("args", {}):
                    raise RuntimeError(
                        "submit_entries foi chamada sem o campo 'itens' "
                        f"esperado — args recebidos: {call.get('args')!r}"
                    )
                return call["args"]["itens"]
        messages.append(response)
        messages.append(
            HumanMessage(
                content=(
                    "Chame agora a tool submit_entries com os itens já "
                    "pesquisados até aqui."
                )
            )
        )
        logger.warning(
            "Pesquisador respondeu sem chamar submit_entries (tentativa %d/%d).",
            attempt + 1,
            max_attempts,
        )

    raise RuntimeError(
        f"Pesquisador não chamou submit_entries após {max_attempts} tentativas."
    )


def _verify_image_url(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Confere de verdade se uma URL de imagem existe e é mesmo uma imagem.

    Nunca confia na palavra do modelo — faz a requisição HTTP de fato,
    igual à checagem manual (curl) usada durante a auditoria de conteúdo.
    """
    headers = {"User-Agent": "AcervoCatolicoBot/1.0 (pesquisador dev-agent)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return False, f"erro de rede: {exc}"

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        return False, f"content-type inesperado: {content_type!r}"
    return True, "ok"


def validate_batch(
    raw_items: list[dict[str, Any]],
    item_model: type[BaseModel],
    existing_slugs: set[str],
) -> tuple[list[BaseModel], list[str]]:
    """Valida e filtra o lote proposto — o portão de autovalidação de verdade.

    Cada item passa por quatro checagens independentes do que o modelo
    afirmou: (1) slug não pode já existir no acervo; (2) 'id' é sempre
    recalculado como '{categoria}:{slug}' — nunca aceito do jeito que o
    modelo propôs (bug real visto na prática: o pesquisador devolveu só o
    slug como id, quebrando a convenção usada em toda entrada existente);
    (3) a URL de imagem, se houver, precisa resolver de verdade como
    imagem (`_verify_image_url`) — se não resolver, a imagem é descartada
    e a entrada segue sem ela, nunca é a entrada inteira que é descartada
    por causa da imagem; (4) o item, já corrigido, precisa validar contra
    o modelo Pydantic real da categoria (`extra="forbid"` no backend barra
    campo inventado; tipos e patterns errados barram o resto).

    Args:
        raw_items: saída bruta de `research_batch`.
        item_model: o mesmo modelo Pydantic passado a `research_batch`.
        existing_slugs: slugs já presentes no arquivo de dados da
            categoria — mutado in-place com os slugs aceitos, então
            chamadas seguintes (outro lote da mesma categoria) já os
            enxergam como ocupados.

    Returns:
        `(entradas_validas, avisos)` — `avisos` é texto pronto para
        revisão humana (o que foi descartado e por quê); nada nesta lista
        de avisos impede a escrita do restante do lote.
    """
    valid: list[BaseModel] = []
    warnings: list[str] = []
    category_field = item_model.model_fields.get("categoria")
    category_value = getattr(category_field.default, "value", None) if category_field else None

    for original in raw_items:
        raw = dict(original)
        slug = raw.get("slug", "<sem slug>")

        if slug in existing_slugs:
            warnings.append(f"descartado '{slug}': slug já existe no acervo")
            continue

        if category_value and slug != "<sem slug>":
            raw["id"] = f"{category_value}:{slug}"

        imagem = raw.get("imagem")
        if imagem:
            ok, reason = _verify_image_url(imagem)
            if not ok:
                warnings.append(f"'{slug}': imagem descartada ({reason}) — {imagem}")
                raw["imagem"] = None
                raw["imagem_credito"] = None

        try:
            entry = item_model.model_validate(raw)
        except ValidationError as exc:
            warnings.append(f"descartado '{slug}': falhou validação — {exc}")
            continue

        valid.append(entry)
        existing_slugs.add(slug)

    return valid, warnings
