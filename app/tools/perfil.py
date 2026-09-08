"""Tool somente de leitura para o especialista financeiro."""

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.perfil import consultar_perfil


@tool
def consultar_perfil_usuario(busca: str, config: RunnableConfig) -> str:
    """Consulta dados do perfil do usuário atual para aconselhamento financeiro."""
    configuravel = (config or {}).get("configurable", {})
    user_id = configuravel.get("user_id")
    if not user_id:
        return "Não foi possível identificar o usuário para consultar o perfil."
    perfil = consultar_perfil(user_id, busca)
    if not perfil:
        return "Nenhum perfil cadastrado para este usuário. Oriente-o a preencher a tela Perfil."
    return (
        f"Renda mensal: R$ {perfil['renda_mensal']:.2f}; objetivo: {perfil['objetivo']}; "
        f"tolerância a risco: {perfil['tolerancia_risco']}; preferências relevantes: "
        f"{perfil['preferencias_relevantes'] or 'não encontradas.'}"
    )


TOOLS_PERFIL = [consultar_perfil_usuario]
