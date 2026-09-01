"""Fluxo LangGraph do Acessor.AI."""

import operator
from typing import Annotated

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from app.guardrail import anonimizar_entrada, guardrail_entrada, guardrail_saida
from app.llms import llm, llm_rapido
from app.memory import iniciar_sessao, salvar_mensagem
from app.prompts import (
    AGENDA_PROMPT_COMPLETO,
    FAQ_PROMPT_COMPLETO,
    FINANCEIRO_PROMPT_COMPLETO,
    ORQUESTRADOR_PROMPT_COMPLETO,
    ROUTER_PROMPT_COMPLETO,
)
from app.tools.financeiro import TOOLS
from app.tools.agenda import TOOLS_AGENDA
from app.tools.faq import faq_retriever
from app.tools.memoria import TOOLS_MEMORIA

router_agent = create_agent(model=llm_rapido, system_prompt=ROUTER_PROMPT_COMPLETO, tools=TOOLS_MEMORIA)
financeiro_agent = create_agent(
    model=llm, system_prompt=FINANCEIRO_PROMPT_COMPLETO, tools=TOOLS + TOOLS_MEMORIA
)
agenda_agent = create_agent(
    model=llm, system_prompt=AGENDA_PROMPT_COMPLETO, tools=TOOLS_AGENDA + TOOLS_MEMORIA
)
orquestrador_agent = create_agent(
    model=llm_rapido, system_prompt=ORQUESTRADOR_PROMPT_COMPLETO
)
# O retriever do FAQ ainda depende de indexação externa; o agente permanece
# disponível para responder pelas instruções de sistema enquanto ela não ocorre.
faq_agent = create_agent(
    model=llm_rapido, system_prompt=FAQ_PROMPT_COMPLETO, tools=[faq_retriever]
)


class Estado(MessagesState):
    agentes_chamados: Annotated[list[str], operator.add]
    rota: str
    mapa_pii: dict[str, str]
    bloqueado: bool


def _texto_mensagem(mensagem: object) -> str:
    conteudo = getattr(mensagem, "content", mensagem)
    return conteudo if isinstance(conteudo, str) else str(conteudo)


def no_guardrail_entrada(estado: Estado) -> dict:
    texto, mapa_pii = anonimizar_entrada(_texto_mensagem(estado["messages"][-1]))
    resultado = guardrail_entrada(texto)
    if resultado["bloqueado"]:
        return {
            "bloqueado": True,
            "mapa_pii": mapa_pii,
            "messages": [AIMessage(content=resultado["mensagem"])],
        }
    return {"bloqueado": False, "mapa_pii": mapa_pii}


def decidir_pos_guardrail_entrada(estado: Estado) -> str:
    return "fim" if estado.get("bloqueado", False) else "roteador"


def no_roteador(estado: Estado, config) -> dict:
    saida = router_agent.invoke({"messages": list(estado["messages"])}, config=config)
    texto = _texto_mensagem(saida["messages"][-1])
    if not texto.strip().startswith("ROUTE="):
        return {"agentes_chamados": ["roteador"], "rota": "fim", "messages": [AIMessage(content=texto)]}

    rota = next(
        (linha.split("=", 1)[1].strip() for linha in texto.splitlines() if linha.startswith("ROUTE=")),
        "fim",
    )
    return {"agentes_chamados": ["roteador"], "rota": rota}


def no_financeiro(estado: Estado, config) -> dict:
    saida = financeiro_agent.invoke({"messages": list(estado["messages"])}, config=config)
    return {"agentes_chamados": ["financeiro"], "messages": [saida["messages"][-1]]}


def no_agenda(estado: Estado, config) -> dict:
    saida = agenda_agent.invoke({"messages": list(estado["messages"])}, config=config)
    return {"agentes_chamados": ["agenda"], "messages": [saida["messages"][-1]]}


def no_faq(estado: Estado, config) -> dict:
    saida = faq_agent.invoke({"messages": list(estado["messages"])}, config=config)
    return {"agentes_chamados": ["faq"], "messages": [saida["messages"][-1]]}


def no_orquestrador(estado: Estado) -> dict:
    saida = orquestrador_agent.invoke({"messages": list(estado["messages"])})
    return {"agentes_chamados": ["orquestrador"], "messages": [saida["messages"][-1]]}


def no_guardrail_saida(estado: Estado) -> dict:
    resultado = guardrail_saida(
        _texto_mensagem(estado["messages"][-1]), estado.get("mapa_pii", {})
    )
    return {"messages": [AIMessage(content=resultado["conteudo"])]}


def decidir_especialista(estado: Estado) -> str:
    return estado.get("rota", "fim") if estado.get("rota") in {"financeiro", "agenda", "faq"} else "fim"


grafo = StateGraph(Estado)
grafo.add_node("guardrail_entrada", no_guardrail_entrada)
grafo.add_node("roteador", no_roteador)
grafo.add_node("financeiro", no_financeiro)
grafo.add_node("agenda", no_agenda)
grafo.add_node("faq", no_faq)
grafo.add_node("orquestrador", no_orquestrador)
grafo.add_node("guardrail_saida", no_guardrail_saida)
grafo.set_entry_point("guardrail_entrada")
grafo.add_conditional_edges("guardrail_entrada", decidir_pos_guardrail_entrada, {"roteador": "roteador", "fim": END})
grafo.add_conditional_edges("roteador", decidir_especialista, {"financeiro": "financeiro", "agenda": "agenda", "faq": "faq", "fim": END})
grafo.add_edge("financeiro", "orquestrador")
grafo.add_edge("agenda", "orquestrador")
grafo.add_edge("faq", "guardrail_saida")
grafo.add_edge("orquestrador", "guardrail_saida")
grafo.add_edge("guardrail_saida", END)

fluxo_agentes = grafo.compile(checkpointer=MemorySaver())


def executar_fluxo_assessor(pergunta_usuario: str, session_id: str) -> tuple[str, list[str]]:
    estado_final = fluxo_agentes.invoke(
        {
            "messages": [{"role": "user", "content": pergunta_usuario}],
            "agentes_chamados": [],
            "rota": "",
            "mapa_pii": {},
            "bloqueado": False,
        },
        config={"configurable": {"thread_id": session_id}},
    )
    resposta_final = _texto_mensagem(estado_final["messages"][-1])

    iniciar_sessao(session_id)
    salvar_mensagem(session_id, "usuario", pergunta_usuario)
    salvar_mensagem(session_id, "assistente", resposta_final)

    return resposta_final, estado_final.get("agentes_chamados", [])
