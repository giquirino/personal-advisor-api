from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR, validar_config
from app.routes.chat import router as chat_router
from app.routes.sessions import router as sessions_router

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

@app.get("/health")
def health() -> dict:
    problemas = validar_config()
    return {
        "status": "ok" if not problemas else "atencao",
        "problemas_de_configuracao": problemas,
    }


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
