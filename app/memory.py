"""Persistencia de sessoes no MongoDB e indice semantico no Qdrant."""

import uuid
from datetime import datetime, timezone

from pymongo import MongoClient
from qdrant_client import models

from app.config import MONGODB_URI
from app.llms import llm_rapido
from app.vectorstore import (
    COLLECTION_MEMORIA,
    garantir_collections,
    gerar_embedding,
    qdrant,
)

_mongo = MongoClient(MONGODB_URI)
db = _mongo["assessor"]
col_sessoes = db["sessoes"]

col_sessoes.create_index("session_id")
col_sessoes.create_index("user_id")
col_sessoes.create_index("iniciada_em")

_PROMPT_RESUMO = """\
Voce e um assistente que resume conversas de assessoria financeira e agenda.
Gere um resumo conciso em 2-4 frases capturando:
- O que o usuario fez (transacoes registradas, eventos agendados)
- O que o usuario perguntou
- Informacoes relevantes mencionadas (valores, datas, categorias)

Responda APENAS com o resumo, sem introducao ou explicacao.

Conversa:
{conversa}
"""

_sessoes_ativas: dict[str, str] = {}


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _formatar_conversa(mensagens: list[dict]) -> str:
    return "\n".join(
        f"{mensagem['role']}: {mensagem['content']}" for mensagem in mensagens
    )


def _gerar_resumo(mensagens: list[dict]) -> str:
    conversa = _formatar_conversa(mensagens)
    return llm_rapido.invoke(
        _PROMPT_RESUMO.format(conversa=conversa)
    ).content.strip()


def _doc_id_da_sessao(session_id: str) -> str | None:
    doc_id = _sessoes_ativas.get(session_id)
    if doc_id:
        return doc_id
    doc = col_sessoes.find_one(
        {"session_id": session_id, "resumo": {"$in": ["", None]}},
        {"_id": 1},
        sort=[("iniciada_em", -1)],
    )
    if not doc:
        return None
    _sessoes_ativas[session_id] = doc["_id"]
    return doc["_id"]


def iniciar_sessao(session_id: str, user_id: str = "usuario_teste") -> None:
    """Cria uma sessao vinculada ao identificador estavel do usuario."""
    if _doc_id_da_sessao(session_id):
        return
    doc_id = str(uuid.uuid4())
    agora = _agora()
    col_sessoes.insert_one({
        "_id": doc_id,
        "session_id": session_id,
        "user_id": user_id,
        "iniciada_em": agora,
        "atualizada_em": agora,
        "resumo": "",
        "mensagens": [],
    })
    _sessoes_ativas[session_id] = doc_id


def salvar_mensagem(
    session_id: str,
    role: str,
    content: str,
    user_id: str = "usuario_teste",
) -> None:
    """Acrescenta uma mensagem a sessao aberta."""
    iniciar_sessao(session_id, user_id=user_id)
    doc_id = _doc_id_da_sessao(session_id)
    col_sessoes.update_one(
        {"_id": doc_id},
        {
            "$push": {"mensagens": {"role": role, "content": content}},
            "$set": {"atualizada_em": _agora(), "user_id": user_id},
        },
    )


def encerrar_sessao(session_id: str) -> str | None:
    """Resume a sessao, persiste o resumo e o indexa semanticamente."""
    doc_id = _doc_id_da_sessao(session_id)
    if not doc_id:
        return None
    doc = col_sessoes.find_one({"_id": doc_id})
    if not doc or not doc.get("mensagens"):
        _sessoes_ativas.pop(session_id, None)
        return None

    resumo = _gerar_resumo(doc["mensagens"])
    user_id = doc.get("user_id", "usuario_teste")
    garantir_collections()
    qdrant.upsert(
        collection_name=COLLECTION_MEMORIA,
        points=[models.PointStruct(
            id=doc_id,
            vector=gerar_embedding(resumo),
            payload={
                "user_id": user_id,
                "session_id": session_id,
                "resumo": resumo,
                "iniciada_em": doc["iniciada_em"].isoformat(),
            },
        )],
    )
    col_sessoes.update_one(
        {"_id": doc_id},
        {"$set": {"resumo": resumo, "atualizada_em": _agora()}},
    )
    _sessoes_ativas.pop(session_id, None)
    return resumo


def recuperar_historico(
    user_id: str,
    busca: str = "",
    limite: int = 3,
) -> list[dict]:
    """Busca resumos semanticamente ou retorna os mais recentes."""
    if busca:
        garantir_collections()
        resultados = qdrant.query_points(
            collection_name=COLLECTION_MEMORIA,
            query=gerar_embedding(busca),
            query_filter=models.Filter(must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                )
            ]),
            limit=limite,
            with_payload=True,
        )
        if resultados.points:
            return [{
                "doc_id": ponto.id,
                "iniciada_em": ponto.payload.get("iniciada_em", ""),
                "resumo": ponto.payload["resumo"],
            } for ponto in resultados.points]

    docs = (
        col_sessoes
        .find(
            {"user_id": user_id, "resumo": {"$nin": ["", None]}},
            {"resumo": 1, "iniciada_em": 1},
        )
        .sort("iniciada_em", -1)
        .limit(limite)
    )
    return [{
        "doc_id": doc["_id"],
        "iniciada_em": doc["iniciada_em"],
        "resumo": doc["resumo"],
    } for doc in docs]


def recuperar_mensagens(doc_id: str) -> list[dict]:
    doc = col_sessoes.find_one({"_id": doc_id}, {"mensagens": 1})
    return doc["mensagens"] if doc else []
