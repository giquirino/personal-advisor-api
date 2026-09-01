"""Cliente Qdrant e geracao centralizada de embeddings."""

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from qdrant_client import QdrantClient, models

from app.config import GEMINI_API_KEY, QDRANT_API_KEY, QDRANT_URL

COLLECTION_MEMORIA = "memoria_resumos"
COLLECTION_FAQ = "faq_chunks"
EMBEDDING_DIM = 768

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

_embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview",
    google_api_key=GEMINI_API_KEY,
)
_collections_prontas = False


def garantir_collections() -> None:
    """Cria as collections e o indice de user_id quando ainda nao existem."""
    global _collections_prontas
    if _collections_prontas:
        return
    configuracao = models.VectorParams(
        size=EMBEDDING_DIM,
        distance=models.Distance.COSINE,
    )
    if not qdrant.collection_exists(COLLECTION_MEMORIA):
        qdrant.create_collection(COLLECTION_MEMORIA, vectors_config=configuracao)
    if not qdrant.collection_exists(COLLECTION_FAQ):
        qdrant.create_collection(COLLECTION_FAQ, vectors_config=configuracao)
    try:
        qdrant.create_payload_index(
            collection_name=COLLECTION_MEMORIA,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    except Exception as erro:
        if "already exists" not in str(erro).lower():
            raise
    _collections_prontas = True


def gerar_embedding(texto: str) -> list[float]:
    """Gera um vetor de 768 dimensoes para um texto."""
    return _embeddings.embed_query(texto, output_dimensionality=EMBEDDING_DIM)


def gerar_embeddings_batch(textos: list[str]) -> list[list[float]]:
    """Gera embeddings em lote usando o mesmo modelo e dimensionalidade."""
    return _embeddings.embed_documents(
        textos, output_dimensionality=EMBEDDING_DIM
    )
