from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """O que o navegador envia no POST /chat."""
    session_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    user_id: str = Field(
        default="usuario_teste",
        description="Identificador estavel do usuario entre sessoes.",
        examples=["usuario_teste"],
    )
    pergunta:   str = Field(..., min_length=1, examples=["gastei 50 reais no mercado"])


class ChatResponse(BaseModel):
    """O que a API devolve no POST /chat."""
    resposta:         str
    agentes_chamados: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    """Ainda não é usado — é do Passo 6 da Etapa 3."""
    session_id: str
    resumo:     str | None = None
