"""Rotas de ciclo de vida das sessões."""

from fastapi import APIRouter, Query

from app.memory import encerrar_sessao
from app.schemas import SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/encerrar", response_model=SessionResponse)
def encerrar(session_id: str, user_id: str = Query(min_length=1)) -> SessionResponse:
    return SessionResponse(session_id=session_id, resumo=encerrar_sessao(session_id, user_id))
