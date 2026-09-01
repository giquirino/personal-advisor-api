from fastapi import APIRouter

from app.graph import executar_fluxo_assessor
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def conversar(requisicao: ChatRequest) -> ChatResponse:
    resposta, agentes = executar_fluxo_assessor(
        requisicao.pergunta, requisicao.session_id
    )
    return ChatResponse(resposta=resposta, agentes_chamados=agentes)
