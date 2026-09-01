"""Indexa o PDF do FAQ no Qdrant. Execute com: python -m app.ingest_faq"""

import uuid

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import models

from app.config import FAQ_PDF_PATH
from app.vectorstore import (
    COLLECTION_FAQ,
    garantir_collections,
    gerar_embeddings_batch,
    qdrant,
)

CHUNK_SIZE = 700
CHUNK_OVERLAP = 150
BATCH_SIZE = 50


def ingerir_faq() -> int:
    """Indexa os chunks de forma idempotente, sem apagar pontos existentes."""
    print(f"[ingest] Carregando PDF: {FAQ_PDF_PATH}")
    docs = PyPDFLoader(str(FAQ_PDF_PATH)).load()
    print(f"[ingest] {len(docs)} pagina(s) carregada(s)")
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    ).split_documents(docs)
    print(f"[ingest] {len(chunks)} chunk(s) gerado(s)")

    garantir_collections()

    for inicio in range(0, len(chunks), BATCH_SIZE):
        lote = chunks[inicio:inicio + BATCH_SIZE]
        textos = [chunk.page_content for chunk in lote]
        fim = inicio + len(lote)
        print(f"[ingest] Gerando embeddings para chunks {inicio + 1}-{fim}...")
        vetores = gerar_embeddings_batch(textos)
        pontos = [models.PointStruct(
            id=str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{FAQ_PDF_PATH.resolve()}:{inicio + indice}:{chunk.page_content}",
            )),
            vector=vetor,
            payload={
                "page_content": chunk.page_content,
                "page_number": chunk.metadata.get("page", 0),
                "source": str(chunk.metadata.get("source", "")),
            },
        ) for indice, (vetor, chunk) in enumerate(zip(vetores, lote))]
        qdrant.upsert(
            collection_name=COLLECTION_FAQ,
            points=pontos,
            wait=True,
        )

    print(f"[ingest] Concluido: {len(chunks)} chunk(s) indexado(s).")
    return len(chunks)


if __name__ == "__main__":
    ingerir_faq()
