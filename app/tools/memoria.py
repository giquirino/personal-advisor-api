"""Ferramentas de memoria de longo prazo dos agentes."""

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from app.memory import recuperar_historico


@tool
def buscar_historico(busca: str, config: RunnableConfig) -> str:
    """Busca algo que o usuario contou em conversas anteriores encerradas."""
    configurable = config.get("configurable", {})
    session_id = configurable.get("user_id") or configurable.get("thread_id")
    if not session_id:
        return "Nao foi possivel identificar o usuario."

    historico = recuperar_historico(session_id, busca=busca, limite=3)
    if not historico:
        return "Nenhuma conversa anterior relevante encontrada."
    return "\n\n".join(
        f"[{item['iniciada_em']:%d/%m/%Y}] {item['resumo']}"
        for item in historico
    )


TOOLS_MEMORIA = [buscar_historico]
