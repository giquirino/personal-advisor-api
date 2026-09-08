"""Persistência e consulta do perfil financeiro estável do usuário."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from pymongo import MongoClient
from qdrant_client import models

from app.config import MONGODB_URI
from app.schemas import PerfilRequest
from app.vectorstore import COLLECTION_PERFIL, garantir_collections, gerar_embedding, qdrant

_mongo: MongoClient | None = None
_indice_criado = False


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _colecao_perfis():
    """Retorna a collection de perfis, com unicidade por usuário."""
    global _mongo, _indice_criado
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI não está configurada. Consulte GET /health.")
    if _mongo is None:
        _mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
    colecao = _mongo["assessor"]["perfis"]
    if not _indice_criado:
        colecao.create_index("user_id", unique=True)
        _indice_criado = True
    return colecao


def _id_do_vetor(user_id: str) -> str:
    """Um ID determinístico torna o novo salvamento uma substituição no Qdrant."""
    return str(uuid5(NAMESPACE_URL, f"assessor/perfil/{user_id}"))


def salvar_perfil(perfil: PerfilRequest) -> dict:
    """Atualiza o documento estruturado e o único vetor de preferências do usuário."""
    dados = perfil.model_dump()
    agora = _agora()
    _colecao_perfis().update_one(
        {"user_id": perfil.user_id},
        {"$set": {**dados, "atualizado_em": agora}, "$setOnInsert": {"criado_em": agora}},
        upsert=True,
    )
    garantir_collections()
    qdrant.upsert(
        collection_name=COLLECTION_PERFIL,
        points=[models.PointStruct(
            id=_id_do_vetor(perfil.user_id), vector=gerar_embedding(perfil.preferencias),
            payload={"user_id": perfil.user_id, "preferencias": perfil.preferencias},
        )],
    )
    return dados


def consultar_perfil(user_id: str, busca: str) -> dict | None:
    """Une o cadastro estruturado ao trecho relevante, sempre do mesmo usuário."""
    perfil = _colecao_perfis().find_one(
        {"user_id": user_id},
        {"_id": 0, "user_id": 1, "renda_mensal": 1, "objetivo": 1, "tolerancia_risco": 1},
    )
    if not perfil:
        return None
    preferencias = ""
    garantir_collections()
    resultado = qdrant.query_points(
        collection_name=COLLECTION_PERFIL, query=gerar_embedding(busca),
        query_filter=models.Filter(must=[models.FieldCondition(
            key="user_id", match=models.MatchValue(value=user_id))]),
        limit=1, with_payload=True,
    )
    if resultado.points:
        preferencias = str(resultado.points[0].payload.get("preferencias", ""))
    return {**perfil, "preferencias_relevantes": preferencias}
