"""Rota de escrita do perfil; não há endpoints de leitura, lista ou exclusão."""

from fastapi import APIRouter

from app.perfil import salvar_perfil
from app.schemas import PerfilRequest, PerfilResponse

router = APIRouter(tags=["perfil"])


@router.post("/perfil", response_model=PerfilResponse)
def criar_ou_atualizar_perfil(requisicao: PerfilRequest) -> PerfilResponse:
    return PerfilResponse(**salvar_perfil(requisicao))
