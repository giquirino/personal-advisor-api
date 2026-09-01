"""Busca semantica do FAQ previamente indexado no Qdrant."""

from langchain.tools import tool

from app.vectorstore import (
    COLLECTION_FAQ,
    garantir_collections,
    gerar_embedding,
    qdrant,
)


@tool
def faq_retriever(question: str) -> str:
    """Busca no FAQ oficial os trechos mais relevantes para uma pergunta."""
    garantir_collections()
    resultados = qdrant.query_points(
        collection_name=COLLECTION_FAQ,
        query=gerar_embedding(question),
        limit=6,
        with_payload=True,
    )
    if not resultados.points:
        return "Nenhum trecho relevante encontrado no FAQ."
    return "\n\n".join(
        ponto.payload["page_content"] for ponto in resultados.points
    )
