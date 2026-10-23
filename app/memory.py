"""PersistÃƒÆ’Ã‚Âªncia de sessÃƒÆ’Ã‚Âµes no MongoDB e ÃƒÆ’Ã‚Â­ndice semÃƒÆ’Ã‚Â¢ntico no Qdrant."""

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

_mongo: MongoClient | None = None
_indices_criados = False


def get_db():
    """ObtÃƒÆ’Ã‚Â©m o banco somente quando uma operaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o realmente precisa dele."""
    global _mongo
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI nÃƒÆ’Ã‚Â£o estÃƒÆ’Ã‚Â¡ configurada. Consulte GET /health.")
    if _mongo is None:
        _mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
    return _mongo["assessor"]


def _get_col_sessoes():
    """Garante os ÃƒÆ’Ã‚Â­ndices apÃƒÆ’Ã‚Â³s a primeira conexÃƒÆ’Ã‚Â£o bem-sucedida ao MongoDB."""
    global _indices_criados
    col_sessoes = get_db()["sessoes"]
    if not _indices_criados:
        col_sessoes.create_index("session_id")
        col_sessoes.create_index("user_id")
        col_sessoes.create_index("iniciada_em")
        _indices_criados = True
    return col_sessoes

_PROMPT_RESUMO = """\
VocÃƒÆ’Ã‚Âª ÃƒÆ’Ã‚Â© um assistente que resume conversas de assessoria financeira e agenda.
Gere um resumo conciso em 2-4 frases capturando:
- O que o usuÃƒÆ’Ã‚Â¡rio fez (transaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Âµes registradas, eventos agendados)
- O que o usuÃƒÆ’Ã‚Â¡rio perguntou
- InformaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Âµes relevantes mencionadas (valores, datas, categorias)

Responda APENAS com o resumo, sem introduÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o ou explicaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o.

Conversa:
{conversa}
"""

_sessoes_ativas: dict[tuple[str, str], str] = {}


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


def _doc_id_da_sessao(session_id: str, user_id: str) -> str | None:
    chave = (session_id, user_id)
    doc_id = _sessoes_ativas.get(chave)
    if doc_id:
        return doc_id
    doc = _get_col_sessoes().find_one(
        {"session_id": session_id, "user_id": user_id, "resumo": {"$in": ["", None]}},
        {"_id": 1},
        sort=[("iniciada_em", -1)],
    )
    if not doc:
        return None
    _sessoes_ativas[chave] = doc["_id"]
    return doc["_id"]


def iniciar_sessao(session_id: str, user_id: str = "usuario_teste") -> None:
    """Cria uma sessÃƒÆ’Ã‚Â£o vinculada ao identificador estÃƒÆ’Ã‚Â¡vel do usuÃƒÆ’Ã‚Â¡rio."""
    if _doc_id_da_sessao(session_id, user_id):
        return
    doc_id = str(uuid.uuid4())
    agora = _agora()
    _get_col_sessoes().insert_one({
        "_id": doc_id,
        "session_id": session_id,
        "user_id": user_id,
        "iniciada_em": agora,
        "atualizada_em": agora,
        "resumo": "",
        "mensagens": [],
    })
    _sessoes_ativas[(session_id, user_id)] = doc_id


def salvar_mensagens(
    session_id: str,
    mensagens: list[dict[str, str]],
    user_id: str = "usuario_teste",
) -> None:
    """Persiste vÃƒÆ’Ã‚Â¡rias mensagens em uma ÃƒÆ’Ã‚Âºnica atualizaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o no MongoDB."""
    iniciar_sessao(session_id, user_id=user_id)
    doc_id = _doc_id_da_sessao(session_id, user_id)
    _get_col_sessoes().update_one(
        {"_id": doc_id},
        {
            "$push": {"mensagens": {"$each": mensagens}},
            "$set": {"atualizada_em": _agora()},
        },
    )


def encerrar_sessao(session_id: str, user_id: str) -> str | None:
    """Resume a sessÃƒÆ’Ã‚Â£o, persiste o resumo e o indexa semanticamente."""
    doc_id = _doc_id_da_sessao(session_id, user_id)
    if not doc_id:
        return None
    doc = _get_col_sessoes().find_one({"_id": doc_id})
    if not doc or not doc.get("mensagens"):
        _sessoes_ativas.pop((session_id, user_id), None)
        return None

    resumo = _gerar_resumo(doc["mensagens"])
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
    _get_col_sessoes().update_one(
        {"_id": doc_id},
        {"$set": {"resumo": resumo, "atualizada_em": _agora()}},
    )
    _sessoes_ativas.pop((session_id, user_id), None)
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
        _get_col_sessoes()
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
