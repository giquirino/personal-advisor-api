"""In-memory metrics for assistant turns and model calls."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

_FUSO = ZoneInfo("America/Sao_Paulo")

# USD por 1 milhão de tokens: (entrada, saída).
PRECO_POR_MILHAO: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
}

# O especialista promete Gemini. Groq neste nó é o with_fallbacks de llms.py.
_NOS_ESPECIALISTA = {"financeiro", "agenda"}
_MODELO_ESPECIALISTA = "gemini-2.5-flash"

LIMITE_TURNOS = 50
LIMITE_P95_MS = 8_000
LIMITE_TAXA_ERRO = 0.05

_lock = threading.Lock()
_inicio_processo = time.time()
_em_andamento = 0
_turnos: list[dict[str, Any]] = []
_chamadas: list[dict[str, Any]] = []
_abertos: dict[str, float] = {}
_runs: dict[str, dict[str, Any]] = {}


def _agora_local() -> str:
    return datetime.now(_FUSO).strftime("%H:%M:%S")


def _nome_modelo(serialized: dict | None, invocation_params: dict | None, resposta_meta: dict | None) -> str:
    candidatos = []
    for fonte in (resposta_meta or {}, invocation_params or {}, (serialized or {}).get("kwargs") or {}):
        for chave in ("model_name", "model"):
            valor = fonte.get(chave)
            if valor:
                candidatos.append(str(valor))
    for nome in candidatos:
        if nome.startswith("models/"):
            nome = nome.split("/", 1)[1]
        return nome
    return "desconhecido"


def _no_do_grafo(metadata: dict | None) -> str:
    """O nó do nosso grafo, não o nó interno do create_agent."""
    metadata = metadata or {}
    ns = str(metadata.get("langgraph_checkpoint_ns") or "")
    candidatos: list[str] = []
    if ns:
        for parte in ns.split("|"):
            candidatos.append(parte.split(":", 1)[0])
    no = metadata.get("langgraph_node")
    if no:
        candidatos.append(str(no))
    for nome in candidatos:
        if nome in _NOS_ESPECIALISTA:
            return nome
    return candidatos[0] if candidatos else ""


def _tokens(message: Any) -> tuple[int, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {
            "input_tokens": getattr(usage, "input_tokens", 0),
            "output_tokens": getattr(usage, "output_tokens", 0),
        }
    entrada = int(usage.get("input_tokens") or 0)
    saida = int(usage.get("output_tokens") or 0)
    if entrada or saida:
        return entrada, saida

    meta = getattr(message, "response_metadata", None) or {}
    bruto = meta.get("token_usage") or meta.get("usage") or {}
    entrada = int(bruto.get("prompt_tokens") or bruto.get("input_tokens") or 0)
    saida = int(bruto.get("completion_tokens") or bruto.get("output_tokens") or 0)
    return entrada, saida


def custo_usd(modelo: str, entrada: int, saida: int) -> float:
    precos = PRECO_POR_MILHAO.get(modelo)
    if precos is None:
        for chave, valor in PRECO_POR_MILHAO.items():
            if chave in modelo:
                precos = valor
                break
    if precos is None:
        return 0.0
    preco_entrada, preco_saida = precos
    return (entrada * preco_entrada + saida * preco_saida) / 1_000_000


def _eh_fallback(no: str, modelo: str) -> bool:
    if no not in _NOS_ESPECIALISTA:
        return False
    return _MODELO_ESPECIALISTA not in modelo


class ColetorChamadas(BaseCallbackHandler):
    """Anota cada chamada de chat model sem guardar o texto do prompt."""

    raise_error = False

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: Any,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        invocation = kwargs.get("invocation_params") or {}
        with _lock:
            _runs[str(run_id)] = {
                "t0": time.perf_counter(),
                "modelo": _nome_modelo(serialized, invocation, None),
                "no": _no_do_grafo(metadata),
                "turno_id": (metadata or {}).get("turno_id"),
            }

    def on_llm_end(self, response: LLMResult, *, run_id: Any, **kwargs: Any) -> None:
        chave = str(run_id)
        with _lock:
            abertura = _runs.pop(chave, None)
        if abertura is None or not abertura.get("turno_id"):
            return

        message = None
        try:
            message = response.generations[0][0].message
        except (IndexError, AttributeError):
            message = None

        entrada, saida = _tokens(message) if message is not None else (0, 0)
        meta = getattr(message, "response_metadata", None) if message is not None else None
        modelo = _nome_modelo(None, None, meta)
        if modelo == "desconhecido":
            modelo = abertura["modelo"]

        latencia_ms = int((time.perf_counter() - abertura["t0"]) * 1000)
        registro = {
            "turno_id": abertura["turno_id"],
            "modelo": modelo,
            "no": abertura["no"],
            "tokens_entrada": entrada,
            "tokens_saida": saida,
            "custo_usd": custo_usd(modelo, entrada, saida),
            "latencia_ms": latencia_ms,
            "fallback": _eh_fallback(abertura["no"], modelo),
        }
        with _lock:
            _chamadas.append(registro)

    def on_llm_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:
        with _lock:
            _runs.pop(str(run_id), None)


coletor = ColetorChamadas()

def abrir_turno() -> str:
    turno_id = uuid.uuid4().hex
    with _lock:
        global _em_andamento
        _em_andamento += 1
        _abertos[turno_id] = time.perf_counter()
    return turno_id


def fechar_turno(turno_id: str, rota: str, status: str) -> None:
    with _lock:
        inicio = _abertos.pop(turno_id, None)
        if inicio is None:
            return
        global _em_andamento
        _em_andamento = max(0, _em_andamento - 1)
        do_turno = [c for c in _chamadas if c["turno_id"] == turno_id]
        _turnos.append({
            "id": turno_id,
            "hora": _agora_local(),
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "rota": rota or "—",
            "status": status,
            "tokens_total": sum(c["tokens_entrada"] + c["tokens_saida"] for c in do_turno),
            "custo_usd": sum(c["custo_usd"] for c in do_turno),
        })
        while len(_turnos) > LIMITE_TURNOS:
            antigo = _turnos.pop(0)
            _chamadas[:] = [c for c in _chamadas if c["turno_id"] != antigo["id"]]


def status_do_estado(estado: dict) -> str:
    """Bloqueio de entrada é o sistema funcionando. Erro fica para a exceção."""
    return "bloqueado" if estado.get("bloqueado") else "ok"


def listar_turnos() -> list[dict[str, Any]]:
    with _lock:
        return [
            {chave: valor for chave, valor in turno.items() if chave != "id"}
            for turno in _turnos
        ]


def listar_chamadas() -> list[dict[str, Any]]:
    with _lock:
        return [
            {chave: valor for chave, valor in chamada.items() if chave != "turno_id"}
            for chamada in _chamadas
        ]


def situacao() -> dict[str, int]:
    with _lock:
        return {
            "em_andamento": _em_andamento,
            "no_ar_segundos": int(time.time() - _inicio_processo),
        }
