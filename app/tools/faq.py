from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from app.config import FAQ_PDF_PATH
from app.llms import faq_embeddings

_db = None


def _obter_indice():
    """Cria o indice somente na primeira consulta, evitando trabalho no startup."""
    global _db
    if _db is None:
        documents = PyPDFLoader(str(FAQ_PDF_PATH)).load()
        chunks = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=150,
        ).split_documents(documents)
        _db = FAISS.from_documents(chunks, faq_embeddings)
    return _db

@tool
def faq_retriever(question: str) -> str:
    """Busca informações relevantes no FAQ."""

    # Busca os trechos mais similares
    results = _obter_indice().similarity_search(question, k=6)

    # Junta os textos encontrados
    context = "\n\n---\n\n".join(
        doc.page_content for doc in results
    )

    return context
