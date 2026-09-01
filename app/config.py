"""Configuração centralizada da aplicação."""

import os
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR aponta para migracao_fastAPI/. É montado a partir da localização
# deste arquivo, sem depender do diretório de onde o uvicorn foi executado.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

load_dotenv(BASE_DIR / ".env")

_faq_pdf_configurado = os.getenv("FAQ_PDF_PATH")
_faq_pdf_path = Path(_faq_pdf_configurado).expanduser() if _faq_pdf_configurado else None
if _faq_pdf_path and not _faq_pdf_path.is_absolute():
    _faq_pdf_path = BASE_DIR / _faq_pdf_path
FAQ_PDF_PATH = _faq_pdf_path or DATA_DIR / "FAQ_assessor_v1.1.pdf"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

OBRIGATORIAS = {
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "GROQ_API_KEY": GROQ_API_KEY,
    "DATABASE_URL": DATABASE_URL,
    "MONGODB_URI": MONGODB_URI,
}


def validar_config() -> list[str]:
    """Devolve a lista de problemas de configuração (vazia = tudo certo)."""
    problemas = []
    for nome, valor in OBRIGATORIAS.items():
        if not valor:
            problemas.append(f"Variável ausente no .env: {nome}")
    if not FAQ_PDF_PATH.exists():
        problemas.append(f"PDF do FAQ não encontrado em: {FAQ_PDF_PATH}")
    return problemas
