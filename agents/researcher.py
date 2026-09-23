"""Agente pesquisador: propõe novas entradas do acervo com base em busca
web real, e valida o que ele propõe antes de qualquer coisa virar arquivo.

Diferença de desenho em relação aos outros papéis (ver `team.py`): este
módulo NÃO usa `AgentExecutor`. A busca web é a tool `TavilySearch` (ver
`agents/llm.py` — precisa de `TAVILY_API_KEY`), uma tool *client-side*
comum: o loop abaixo executa a chamada de verdade e devolve o resultado
como `ToolMessage`, igual a qualquer outra tool deste projeto. Isso
substitui a antiga tool `web_search` nativa da Anthropic (server-side,
sem equivalente no DeepSeek) — este papel já foi hardcoded em
`provider="anthropic"` por causa dela; agora segue `LLM_PROVIDER` como
todo o resto do time (ver `agents/llm.py::build_chat_model`). A outra
tool que este módulo intercepta é `submit_entries`, a saída final
estruturada — por isso o loop ainda é próprio (chamar o modelo, executar
buscas se pedidas, checar se já chamou `submit_entries`, senão insistir),
não o loop genérico do LangChain.

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
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_tavily import TavilySearch
from pydantic import BaseModel, ValidationError, create_model

from agents.llm import build_chat_model
from agents.quality import record_quality
from agents.team import _system_message
from agents.usage import usage_handler

logger = logging.getLogger(__name__)

ROLE = "pesquisador"


class SearchUnavailableError(RuntimeError):
    """A busca web não está funcionando (cota esgotada, chave inválida).

    Falha alta e imediata de propósito: sem busca o modelo se recusa a
    propor entrada de memória (regra 1 da persona) e gasta as
    `max_iterations` inteiras sem chamar `submit_entries`. Quem roda lotes
    em série deve parar TUDO ao receber isto, não só pular o lote.
    """

# Descrição do papel — mesma convenção de agents.team.ROLES, mas vive
# aqui (não lá) porque este papel não segue o padrão create_agent /
# create_agent_with_tools dos demais. Também não inclui standards/general.md
# (via _build_persona) de propósito: aquele arquivo fala de instalar
# dependências, rodar lint/testes de CÓDIGO — não se aplica a uma tarefa
# que só produz dados JSON. As regras de autovalidação equivalentes para
# este papel estão listadas abaixo, e a validação de verdade é código
# (validate_batch), não instrução de prompt.
_PERSONA = (
    "# PAPEL\n\n"
    "Você é o Pesquisador de Conteúdo Católico Tradicional do time: um "
    "pesquisador sênior de história da Igreja, teologia e hagiografia. "
    "Sua função é encontrar, com a ferramenta de busca web, fatos REAIS e "
    "verificáveis para novas entradas do Acervo Católico e propô-las pela "
    "tool `submit_entries`. Você nunca inventa fato, data ou imagem.\n\n"
    "# COMO PESQUISAR\n\n"
    "Para cada lote, siga este ciclo antes de propor qualquer coisa:\n"
    "1. Escreva um parágrafo curto dizendo o que as entradas precisam "
    "conter para serem completas e úteis (fatos, datas, personagens, "
    "fontes, imagem).\n"
    "2. A partir desse parágrafo, defina de 2 a 5 queries e faça as "
    "buscas. Varie o ângulo: uma query geral, outra em fonte primária ou "
    "documento oficial, outra em Wikimedia Commons para imagem.\n"
    "3. Analise os resultados: o que foi confirmado por mais de uma "
    "fonte, o que divergiu, o que ficou sem resposta.\n"
    "4. Escreva um parágrafo curto de reflexão apontando o que ainda "
    "poderia ser aprofundado (data incerta, fonte fraca, imagem ausente).\n"
    "5. Volte ao passo 1 se a reflexão mostrar lacuna relevante; senão, "
    "siga para a entrega.\n\n"
    "Só depois de terminar todas as buscas que julgar necessárias, chame "
    "`submit_entries`. O objetivo é conteúdo que valha ser lido: prefira o "
    "detalhe específico e pouco conhecido (o contexto do evento, a "
    "controvérsia, o número exato, a citação de fonte primária) ao "
    "resumo genérico que qualquer enciclopédia já traz. Curiosidade só "
    "entra se estiver apoiada em fonte real.\n\n"
    "# REGRAS INEGOCIÁVEIS\n\n"
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
    "9. Chame `submit_entries` UMA única vez, com todos os itens juntos."
)

# Acrescentado à persona no modo de aprofundamento (entradas que JÁ existem).
# As regras 1-5, 7 e 8 continuam valendo; a 6 (slug novo) é trocada pela
# regra abaixo, porque aqui o slug tem de ser o mesmo.
_ENRICH_NOTE = (
    "\n\n# MODO APROFUNDAMENTO\n\n"
    "Nesta tarefa as entradas JÁ EXISTEM no acervo e vêm no texto da "
    "tarefa. A regra 6 não se aplica: devolva cada item com o MESMO 'id' e "
    "'slug' recebidos, e mantenha inalterados título, categoria e os "
    "campos específicos da categoria. Você pode reescrever 'corpo', "
    "'resumo', 'fontes', 'tags', 'imagem' e 'imagem_credito'.\n"
    "- O novo 'corpo' deve ser mais profundo que o atual, nunca mais "
    "curto: preserve tudo que já está correto e acrescente contexto "
    "histórico, personagens, datas, controvérsias e citações de fonte "
    "primária que você confirmou por busca.\n"
    "- Se a busca contradisser algo do texto atual, corrija e diga "
    "isso na sua reflexão; se não achar nada novo e confiável, devolva o "
    "texto atual sem inventar."
)


def _web_search_tool() -> BaseTool:
    """Tool de busca web client-side (Tavily — precisa de `TAVILY_API_KEY`
    no `.env`) — substitui a antiga `web_search` nativa da Anthropic (ver
    docstring do módulo). `search_depth="advanced"` e `include_images=True`
    porque o Pesquisador precisa tanto de conteúdo textual quanto de URLs de
    imagem real (Wikimedia Commons etc.) para propor uma entrada completa.
    """
    return TavilySearch(max_results=5, search_depth="advanced", include_images=True)


def _submit_entries_tool(item_model: type[BaseModel]) -> StructuredTool:
    """Tool "de verdade" (client-side): a saída final e estruturada do lote.

    O schema de cada item vem do próprio modelo Pydantic REAL da categoria
    (ver `research_batch`) — a mesma fonte usada depois para validar, então
    o modelo nunca vê um contrato diferente do que será exigido dele. A
    função associada nunca é chamada de fato: `research_batch` intercepta
    os argumentos direto de `response.tool_calls`, igual fazia com o dict
    de tool "cru" da Anthropic antes desta função existir.
    """
    args_model = create_model("SubmitEntriesArgs", itens=(list[item_model], ...))

    def _submit(**_kwargs: Any) -> str:
        return "ok"

    return StructuredTool.from_function(
        func=_submit,
        name="submit_entries",
        description=(
            "Envia o lote final de entradas pesquisadas para esta tarefa, "
            "uma por item, depois de concluída toda a pesquisa necessária."
        ),
        args_schema=args_model,
    )


def research_batch(
    task: str,
    item_model: type[BaseModel],
    *,
    max_iterations: int = 30,
    max_search_calls: int = 15,
    max_tokens: int = 16000,
    model: str | None = None,
    persona: str = _PERSONA,
) -> list[dict[str, Any]]:
    """Pesquisa e propõe um lote de entradas — SEM validar (ver `validate_batch`).

    Args:
        task: descrição da tarefa (ex.: "pesquise os concílios ecumênicos
            que faltam: Constantinopla I, Éfeso, ... Slugs já existentes:
            niceia-i, trento, vaticano-ii.").
        item_model: o modelo Pydantic REAL da categoria (ex.: `Concilio`,
            importado do backend) — vira tanto o schema da tool quanto,
            depois, o validador em `validate_batch`.
        max_iterations: teto de idas e voltas com o modelo (cada busca ou
            resposta sem `submit_entries` consome uma) — proteção contra
            loop de busca sem fim, não um limite de qualidade.
        max_search_calls: teto de buscas web reais no lote inteiro (custo
            de API da Tavily) — depois de esgotado, o modelo é instruído a
            chamar `submit_entries` com o que já tem em vez de buscar mais.
        model: ID do modelo a usar. Se omitido, usa o padrão do provedor
            ativo (`LLM_PROVIDER`) — ver `agents/llm.py::build_chat_model`.
        persona: prompt de sistema. Padrão: `_PERSONA`; o aprofundamento
            de entradas existentes passa `_PERSONA + _ENRICH_NOTE`.
        max_tokens: teto de saída do modelo. Um lote com muitos itens
            (bug real já visto: 18 concílios numa chamada só, 200k tokens
            de entrada por causa dos resultados de busca acumulados)
            estoura esse teto e corta a resposta no meio do JSON da tool
            call — prefira lotes menores (3-6 itens) a subir este valor
            sem necessidade.

    Returns:
        A lista bruta de itens (dicts) que o modelo propôs — ainda não
        validada nem verificada. Gasta tokens de API reais a cada chamada
        (e uma busca real por chamada de `tavily_search`).

    Raises:
        RuntimeError: se uma resposta for cortada por limite de tokens
            (`stop_reason`/`finish_reason` de truncamento), se
            `submit_entries` vier sem o campo `itens`, ou se o modelo não
            chamar `submit_entries` depois de `max_iterations` idas e
            voltas.
    """
    search_tool = _web_search_tool()
    submit_tool = _submit_entries_tool(item_model)
    chat_model = (
        build_chat_model(max_tokens=max_tokens, model=model)
        .bind_tools([search_tool, submit_tool])
        .with_config(callbacks=[usage_handler], tags=[f"role:{ROLE}"])
    )

    messages: list[Any] = [_system_message(persona), HumanMessage(content=task)]
    search_calls_left = max_search_calls

    for iteration in range(max_iterations):
        response = chat_model.invoke(messages)
        messages.append(response)

        # Nomes diferentes por provedor pro mesmo evento (truncamento por
        # teto de tokens): Anthropic usa "stop_reason"="max_tokens",
        # OpenAI-compatível (DeepSeek) usa "finish_reason"="length". Não dá
        # pra confiar em tool_calls daqui: o pedido era grande demais para
        # max_tokens, possivelmente cortado no meio do JSON de uma tool
        # call — falhar alto e claro é melhor que um KeyError sem contexto
        # (bug real já visto neste projeto, ver ARCHITECTURE.md).
        truncated = response.response_metadata.get(
            "stop_reason"
        ) == "max_tokens" or response.response_metadata.get("finish_reason") == "length"
        if truncated:
            raise RuntimeError(
                "Resposta cortada por limite de tokens — o lote pedido é "
                "grande demais para uma chamada só. Peça menos itens por "
                "vez ou aumente max_tokens."
            )

        if not response.tool_calls:
            # Tool call com JSON inválido (visto no DeepSeek) cai em
            # `invalid_tool_calls`, mas a mensagem continua carregando o
            # tool_call original no histórico: sem um ToolMessage por id, o
            # próximo request volta 400 ("tool_calls must be followed by
            # tool messages").
            for bad in response.invalid_tool_calls:
                messages.append(
                    ToolMessage(
                        content="Argumentos inválidos (JSON malformado) — refaça a chamada.",
                        tool_call_id=bad["id"],
                    )
                )
            messages.append(
                HumanMessage(
                    content=(
                        "Chame agora a tool submit_entries com os itens já "
                        "pesquisados até aqui."
                    )
                )
            )
            logger.warning(
                "Pesquisador respondeu sem chamar nenhuma tool (iteração %d/%d).",
                iteration + 1,
                max_iterations,
            )
            continue

        submit_call = None
        for call in response.tool_calls:
            if call["name"] == "submit_entries":
                submit_call = call
                continue
            # Qualquer outra tool chamada é a busca — executada de verdade
            # aqui (client-side), diferente da antiga web_search server-side
            # da Anthropic (ver docstring do módulo).
            if search_calls_left <= 0:
                result_text = (
                    "Limite de buscas deste lote atingido — chame "
                    "submit_entries com o que você já apurou até aqui."
                )
            else:
                search_calls_left -= 1
                result = search_tool.invoke(call["args"])
                # TavilySearch não levanta exceção: devolve {"error": ...}
                # (ex.: "Error 432 ... plan's set usage limit").
                if isinstance(result, dict) and result.get("error"):
                    raise SearchUnavailableError(f"busca web falhou: {result['error']}")
                result_text = (
                    result if isinstance(result, str)
                    else json.dumps(result, ensure_ascii=False, default=str)
                )
            messages.append(ToolMessage(content=result_text, tool_call_id=call["id"]))

        if submit_call is not None:
            if "itens" not in submit_call.get("args", {}):
                raise RuntimeError(
                    "submit_entries foi chamada sem o campo 'itens' "
                    f"esperado — args recebidos: {submit_call.get('args')!r}"
                )
            return submit_call["args"]["itens"]

    raise RuntimeError(
        f"Pesquisador não chamou submit_entries após {max_iterations} iterações."
    )


def _verify_image_url(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Confere de verdade se uma URL de imagem existe e é mesmo uma imagem.

    Nunca confia na palavra do modelo — faz a requisição HTTP de fato,
    igual à checagem manual (curl) usada durante a auditoria de conteúdo.
    """
    # A Wikimedia responde 403 a User-Agent sem contato (verificado com httpx).
    headers = {"User-Agent": "AcervoCatolicoBot/1.0 (contato: oliveiravictordev@gmail.com) httpx"}
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
    *,
    model: str = "",
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

    Ao final, registra um resumo do lote (proposto vs. válido, motivo dos
    descartes) via `agents.quality.record_quality` — é o dado que alimenta
    `quality_dashboard.py`. Chamado incondicionalmente (não é opcional):
    o ponto inteiro é nunca esquecer de medir acertividade num lote real.

    Args:
        raw_items: saída bruta de `research_batch`.
        item_model: o mesmo modelo Pydantic passado a `research_batch`.
        existing_slugs: slugs já presentes no arquivo de dados da
            categoria — mutado in-place com os slugs aceitos, então
            chamadas seguintes (outro lote da mesma categoria) já os
            enxergam como ocupados.
        model: ID do modelo que propôs o lote (ex.: o `model` passado a
            `research_batch`) — só para o registro de qualidade, não afeta
            a validação. Vazio por padrão para quem chama `validate_batch`
            isoladamente (ex.: testes) sem se importar com o dashboard.

    Returns:
        `(entradas_validas, avisos)` — `avisos` é texto pronto para
        revisão humana (o que foi descartado e por quê); nada nesta lista
        de avisos impede a escrita do restante do lote.
    """
    valid: list[BaseModel] = []
    warnings: list[str] = []
    discarded_duplicate_slug = 0
    discarded_validation_error = 0
    images_discarded = 0
    category_field = item_model.model_fields.get("categoria")
    category_value = getattr(category_field.default, "value", None) if category_field else None

    for original in raw_items:
        raw = dict(original)
        slug = raw.get("slug", "<sem slug>")

        if slug in existing_slugs:
            warnings.append(f"descartado '{slug}': slug já existe no acervo")
            discarded_duplicate_slug += 1
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
                images_discarded += 1

        try:
            entry = item_model.model_validate(raw)
        except ValidationError as exc:
            warnings.append(f"descartado '{slug}': falhou validação — {exc}")
            discarded_validation_error += 1
            continue

        valid.append(entry)
        existing_slugs.add(slug)

    record_quality(
        role=ROLE,
        model=model,
        items_proposed=len(raw_items),
        items_valid=len(valid),
        discarded_duplicate_slug=discarded_duplicate_slug,
        discarded_validation_error=discarded_validation_error,
        images_discarded=images_discarded,
    )

    return valid, warnings


# Campos que o aprofundamento pode alterar; todo o resto vem do original.
ENRICHABLE_FIELDS = ("corpo", "resumo", "fontes", "tags", "imagem", "imagem_credito")


def merge_enrichment(
    raw_items: list[dict[str, Any]],
    item_model: type[BaseModel],
    originals: dict[str, dict[str, Any]],
    *,
    model: str = "",
) -> tuple[list[BaseModel], list[str]]:
    """Valida o aprofundamento de entradas EXISTENTES e devolve as versões novas.

    Contraparte de `validate_batch` para o modo de aprofundamento: em vez
    de rejeitar slug repetido, exige que o slug seja um dos originais
    (`originals`, indexado por slug) e aplica por cima do original só os
    campos de `ENRICHABLE_FIELDS` — id, slug, título e campos específicos
    da categoria nunca são aceitos do modelo. Um item é descartado (e o
    original permanece) se o 'corpo' novo for mais curto que o atual, ou
    se falhar na validação Pydantic real. Imagem nova é verificada por
    HTTP; se não resolver, mantém a imagem que já existia.
    """
    merged: list[BaseModel] = []
    warnings: list[str] = []
    discarded_validation_error = 0
    images_discarded = 0

    for proposed in raw_items:
        slug = proposed.get("slug", "<sem slug>")
        original = originals.get(slug)
        if original is None:
            warnings.append(f"descartado '{slug}': slug não é de uma entrada existente")
            discarded_validation_error += 1
            continue

        candidate = dict(original)
        for field in ENRICHABLE_FIELDS:
            if field in proposed:
                candidate[field] = proposed[field]

        if len(candidate.get("corpo") or "") < len(original.get("corpo") or ""):
            warnings.append(f"descartado '{slug}': corpo novo é mais curto que o atual")
            discarded_validation_error += 1
            continue

        new_image = candidate.get("imagem")
        if new_image and new_image != original.get("imagem"):
            ok, reason = _verify_image_url(new_image)
            if not ok:
                warnings.append(
                    f"'{slug}': imagem nova descartada ({reason}), mantida a atual — {new_image}"
                )
                candidate["imagem"] = original.get("imagem")
                candidate["imagem_credito"] = original.get("imagem_credito")
                images_discarded += 1

        try:
            merged.append(item_model.model_validate(candidate))
        except ValidationError as exc:
            warnings.append(f"descartado '{slug}': falhou validação — {exc}")
            discarded_validation_error += 1

    record_quality(
        role=ROLE,
        model=model,
        items_proposed=len(raw_items),
        items_valid=len(merged),
        discarded_duplicate_slug=0,
        discarded_validation_error=discarded_validation_error,
        images_discarded=images_discarded,
    )

    return merged, warnings
