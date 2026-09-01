"""Rotas de ciclo de vida das sessoes."""

from fastapi import APIRouter

from app.memory import encerrar_sessao
from app.schemas import SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/encerrar", response_model=SessionResponse)
def encerrar(session_id: str) -> SessionResponse:
    return SessionResponse(session_id=session_id, resumo=encerrar_sessao(session_id))
