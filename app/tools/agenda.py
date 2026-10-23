"""Ferramentas persistentes de agenda armazenadas no MongoDB."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.memory import get_db

_indice_criado = False


def _get_col_eventos():
    """Obtém a coleção e cria seu índice apenas após conectar ao MongoDB."""
    global _indice_criado
    col_eventos = get_db()["eventos"]
    if not _indice_criado:
        col_eventos.create_index([("user_id", 1), ("inicio", 1)])
        _indice_criado = True
    return col_eventos


def _user_id(config: RunnableConfig) -> str | None:
    configurable = config.get("configurable", {})
    return configurable.get("user_id") or configurable.get("thread_id")


def _instante(valor: str) -> datetime:
    instante = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("Data e hora devem incluir o fuso horário.")
    return instante.astimezone(timezone.utc)


def _conflito(eventos, inicio: datetime, fim: datetime, ignorar_id: str | None = None):
    for evento in eventos:
        if evento["_id"] == ignorar_id:
            continue
        if _instante(evento["inicio"]) < fim and _instante(evento["fim"]) > inicio:
            return evento
    return None


class CriarEventoArgs(BaseModel):
    titulo: str = Field(..., min_length=1)
    inicio: str = Field(..., description="Data e hora ISO 8601, por exemplo 2026-09-01T14:00:00-03:00.")
    fim: str = Field(..., description="Data e hora ISO 8601 posterior ao início.")
    local: Optional[str] = None
    participantes: list[str] = Field(default_factory=list)
    lembrete: Optional[str] = None


@tool("criar_evento", args_schema=CriarEventoArgs)
def criar_evento(
    titulo: str,
    inicio: str,
    fim: str,
    config: RunnableConfig,
    local: str | None = None,
    participantes: list[str] | None = None,
    lembrete: str | None = None,
) -> dict:
    """Cria um compromisso depois que os dados necessários foram confirmados."""
    user_id = _user_id(config)
    if not user_id:
        return {"status": "error", "message": "Usuário não identificado."}
    try:
        inicio_utc, fim_utc = _instante(inicio), _instante(fim)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    if fim_utc <= inicio_utc:
        return {"status": "error", "message": "O fim deve ser posterior ao início."}

    col_eventos = _get_col_eventos()
    conflito = _conflito(col_eventos.find({"user_id": user_id, "status": "ativo"}), inicio_utc, fim_utc)
    if conflito:
        return {
            "status": "conflict",
            "message": "Existe um compromisso nesse horário.",
            "evento": conflito,
        }

    evento = {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "titulo": titulo,
        "inicio": inicio_utc.isoformat(),
        "fim": fim_utc.isoformat(),
        "local": local,
        "participantes": participantes or [],
        "lembrete": lembrete,
        "status": "ativo",
        "criado_em": datetime.now(timezone.utc),
    }
    col_eventos.insert_one(evento)
    return {"status": "ok", "evento": evento}


class ListarEventosArgs(BaseModel):
    de: Optional[str] = Field(default=None, description="Inicio ISO 8601 opcional.")
    ate: Optional[str] = Field(default=None, description="Fim ISO 8601 opcional.")
    limite: int = Field(default=20, ge=1, le=100)


@tool("listar_eventos", args_schema=ListarEventosArgs)
def listar_eventos(
    config: RunnableConfig,
    de: str | None = None,
    ate: str | None = None,
    limite: int = 20,
) -> dict:
    """Lista compromissos ativos, podendo filtrar por uma janela de tempo."""
    user_id = _user_id(config)
    if not user_id:
        return {"status": "error", "message": "Usuário não identificado."}
    filtro: dict = {"user_id": user_id, "status": "ativo"}
    try:
        de_utc = _instante(de) if de else None
        ate_utc = _instante(ate) if ate else None
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    eventos = sorted(
        (
            evento for evento in _get_col_eventos().find(filtro)
            if (de_utc is None or _instante(evento["inicio"]) >= de_utc)
            and (ate_utc is None or _instante(evento["inicio"]) <= ate_utc)
        ),
        key=lambda evento: _instante(evento["inicio"]),
    )[:limite]
    return {"status": "ok", "eventos": eventos}


class AtualizarEventoArgs(BaseModel):
    evento_id: str
    titulo: Optional[str] = None
    inicio: Optional[str] = None
    fim: Optional[str] = None
    local: Optional[str] = None
    lembrete: Optional[str] = None


@tool("atualizar_evento", args_schema=AtualizarEventoArgs)
def atualizar_evento(
    evento_id: str,
    config: RunnableConfig,
    titulo: str | None = None,
    inicio: str | None = None,
    fim: str | None = None,
    local: str | None = None,
    lembrete: str | None = None,
) -> dict:
    """Atualiza os campos informados de um compromisso existente."""
    user_id = _user_id(config)
    alteracoes = {
        chave: valor
        for chave, valor in {
            "titulo": titulo, "inicio": inicio, "fim": fim,
            "local": local, "lembrete": lembrete,
        }.items()
        if valor is not None
    }
    if not user_id:
        return {"status": "error", "message": "Usuário não identificado."}
    if not alteracoes:
        return {"status": "error", "message": "Nenhuma alteração informada."}
    col_eventos = _get_col_eventos()
    evento = col_eventos.find_one({"_id": evento_id, "user_id": user_id, "status": "ativo"})
    if not evento:
        return {"status": "error", "message": "Evento não encontrado."}
    if inicio is not None or fim is not None:
        try:
            inicio_utc = _instante(inicio or evento["inicio"])
            fim_utc = _instante(fim or evento["fim"])
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        if fim_utc <= inicio_utc:
            return {"status": "error", "message": "O fim deve ser posterior ao início."}
        conflito = _conflito(
            col_eventos.find({"user_id": user_id, "status": "ativo"}),
            inicio_utc, fim_utc, evento_id,
        )
        if conflito:
            return {"status": "conflict", "message": "Existe um compromisso nesse horário.", "evento": conflito}
        alteracoes.update({"inicio": inicio_utc.isoformat(), "fim": fim_utc.isoformat()})
    resultado = col_eventos.update_one(
        {"_id": evento_id, "user_id": user_id, "status": "ativo"},
        {"$set": alteracoes},
    )
    if not resultado.matched_count:
        return {"status": "error", "message": "Evento não encontrado."}
    return {"status": "ok", "evento": col_eventos.find_one({"_id": evento_id})}


class CancelarEventoArgs(BaseModel):
    evento_id: str


@tool("cancelar_evento", args_schema=CancelarEventoArgs)
def cancelar_evento(evento_id: str, config: RunnableConfig) -> dict:
    """Cancela um compromisso que o usuário confirmou que deseja cancelar."""
    user_id = _user_id(config)
    if not user_id:
        return {"status": "error", "message": "Usuário não identificado."}
    resultado = _get_col_eventos().update_one(
        {"_id": evento_id, "user_id": user_id, "status": "ativo"},
        {"$set": {"status": "cancelado", "cancelado_em": datetime.now(timezone.utc)}},
    )
    if not resultado.matched_count:
        return {"status": "error", "message": "Evento não encontrado."}
    return {"status": "ok", "evento_id": evento_id}


TOOLS_AGENDA = [criar_evento, listar_eventos, atualizar_evento, cancelar_evento]
