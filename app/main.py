import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from qdrant_client import QdrantClient

from app.config import (
    DATABASE_URL,
    FAQ_PDF_PATH,
    FRONTEND_DIR,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    MONGODB_URI,
    QDRANT_API_KEY,
    QDRANT_URL,
    validar_config,
)
from app.routes.chat import router as chat_router
from app.routes.sessions import router as sessions_router
from app.routes.perfil import router as perfil_router
from app.schemas import HealthCheck, HealthResponse

for _problema in validar_config():
    print(f"[config] ATENÇÃO: {_problema}")

app = FastAPI(
    title="Acessor IA",
    description="Acessor financeiro e de agenda com LangChain e LangGraph",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(perfil_router)

def _not_configured(variable: str) -> HealthCheck:
    return HealthCheck(
        status="not_configured",
        message=f"Variável ausente no .env: {variable}",
    )


@app.get("/health", response_model=HealthResponse, tags=["infraestrutura"])
def health() -> HealthResponse:
    """Verifica configuração e conectividade das dependências essenciais."""
    checks: dict[str, HealthCheck] = {}

    checks["gemini"] = (
        HealthCheck(status="ok", message="GEMINI_API_KEY configurada.")
        if GEMINI_API_KEY else _not_configured("GEMINI_API_KEY")
    )
    checks["groq"] = (
        HealthCheck(status="ok", message="GROQ_API_KEY configurada.")
        if GROQ_API_KEY else _not_configured("GROQ_API_KEY")
    )
    checks["faq_pdf"] = (
        HealthCheck(status="ok", message="PDF do FAQ encontrado.")
        if FAQ_PDF_PATH.exists()
        else HealthCheck(status="unavailable", message="PDF do FAQ não encontrado.")
    )

    if not MONGODB_URI:
        checks["mongodb"] = _not_configured("MONGODB_URI")
    else:
        try:
            MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3_000).admin.command("ping")
            checks["mongodb"] = HealthCheck(status="ok", message="MongoDB acessível.")
        except Exception:
            checks["mongodb"] = HealthCheck(
                status="unavailable", message="MongoDB não acessível. Verifique URI, rede e TLS."
            )

    if not DATABASE_URL:
        checks["postgresql"] = _not_configured("DATABASE_URL")
    else:
        try:
            with psycopg2.connect(DATABASE_URL, connect_timeout=3):
                pass
            checks["postgresql"] = HealthCheck(status="ok", message="PostgreSQL acessível.")
        except Exception:
            checks["postgresql"] = HealthCheck(
                status="unavailable", message="PostgreSQL não acessível. Verifique URL e rede."
            )

    if not QDRANT_URL:
        checks["qdrant"] = _not_configured("QDRANT_URL")
    elif not QDRANT_API_KEY:
        checks["qdrant"] = _not_configured("QDRANT_API_KEY")
    else:
        try:
            QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=3).get_collections()
            checks["qdrant"] = HealthCheck(status="ok", message="Qdrant acessível.")
        except Exception:
            checks["qdrant"] = HealthCheck(
                status="unavailable", message="Qdrant não acessível. Verifique URL, chave e rede."
            )

    status = "ok" if all(check.status == "ok" for check in checks.values()) else "degraded"
    return HealthResponse(status=status, checks=checks)


_arquivo_frontend = FRONTEND_DIR / "index.html"
_frontend_disponivel = (
    _arquivo_frontend.is_file() and _arquivo_frontend.stat().st_size > 0
)

if _frontend_disponivel:
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/infra", status_code=503, tags=["infraestrutura"])
    def status_infra() -> dict:
        return {
            "status": "erro",
            "mensagem": "Frontend não foi criado ou o arquivo index.html está vazio.",
        }
