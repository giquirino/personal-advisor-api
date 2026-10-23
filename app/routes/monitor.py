"""Aggregate in-process turn and model metrics for the monitoring dashboard."""

import math

from fastapi import APIRouter

from app.observabilidade import (
    LIMITE_P95_MS,
    LIMITE_TAXA_ERRO,
    listar_chamadas,
    listar_turnos,
    situacao,
)

router = APIRouter(tags=["monitor"])


def _percentil_95(valores: list[int]) -> int:
    """Nearest-rank: o menor valor que cobre 95% das amostras, já ordenadas."""
    if not valores:
        return 0
    ordenados = sorted(valores)
    indice = math.ceil(0.95 * len(ordenados)) - 1
    return ordenados[min(max(indice, 0), len(ordenados) - 1)]


def _media(valores: list[float]) -> float:
    if not valores:
        return 0.0
    return sum(valores) / len(valores)


def _agrupar(chamadas: list[dict], chave: str) -> dict[str, list[dict]]:
    grupos: dict[str, list[dict]] = {}
    for item in chamadas:
        grupos.setdefault(item[chave], []).append(item)
    return grupos


def montar_painel() -> dict:
    turnos = listar_turnos()
    chamadas = listar_chamadas()
    estado = situacao()

    latencias = [t["latencia_ms"] for t in turnos]
    erros = sum(1 for t in turnos if t["status"] == "erro")
    bloqueios = sum(1 for t in turnos if t["status"] == "bloqueado")
    taxa_erro = (erros / len(turnos)) if turnos else 0.0
    p95 = _percentil_95(latencias)

    tokens_entrada = sum(c["tokens_entrada"] for c in chamadas)
    tokens_saida = sum(c["tokens_saida"] for c in chamadas)
    custo = sum(c["custo_usd"] for c in chamadas)

    por_modelo_bruto = _agrupar(chamadas, "modelo")
    mais_usado = "—"
    if por_modelo_bruto:
        mais_usado = max(
            por_modelo_bruto,
            key=lambda nome: (
                len(por_modelo_bruto[nome]),
                sum(i["tokens_entrada"] + i["tokens_saida"] for i in por_modelo_bruto[nome]),
            ),
        )

    por_modelo = []
    for modelo, itens in por_modelo_bruto.items():
        por_modelo.append({
            "modelo": modelo,
            "chamadas": len(itens),
            "tokens_entrada": sum(i["tokens_entrada"] for i in itens),
            "tokens_saida": sum(i["tokens_saida"] for i in itens),
            "custo_usd": round(sum(i["custo_usd"] for i in itens), 6),
            "latencia_media_ms": round(_media([i["latencia_ms"] for i in itens])),
        })
    por_modelo.sort(key=lambda linha: linha["custo_usd"], reverse=True)

    por_rota_bruto = _agrupar(turnos, "rota")
    por_rota = []
    for rota, itens in por_rota_bruto.items():
        por_rota.append({
            "rota": rota,
            "turnos": len(itens),
            "erros": sum(1 for i in itens if i["status"] == "erro"),
            "latencia_media_ms": round(_media([i["latencia_ms"] for i in itens])),
            "custo_usd": round(sum(i["custo_usd"] for i in itens), 6),
        })
    por_rota.sort(key=lambda linha: linha["turnos"], reverse=True)

    custo_acumulado = 0.0
    serie_custo = []
    for turno in turnos:
        custo_acumulado += turno["custo_usd"]
        serie_custo.append({
            "hora": turno["hora"],
            "custo_acumulado_usd": round(custo_acumulado, 6),
        })

    return {
        "slo": {
            "latencia_p95_limite_ms": LIMITE_P95_MS,
            "taxa_erro_limite": LIMITE_TAXA_ERRO,
        },
        "resumo": {
            "turnos": len(turnos),
            "em_andamento": estado["em_andamento"],
            "no_ar_segundos": estado["no_ar_segundos"],
            "taxa_erro": round(taxa_erro, 4),
            "bloqueios": bloqueios,
            "latencia_media_ms": round(_media(latencias)),
            "latencia_p95_ms": p95,
            "slo_ok": p95 <= LIMITE_P95_MS and taxa_erro <= LIMITE_TAXA_ERRO,
            "tokens_entrada": tokens_entrada,
            "tokens_saida": tokens_saida,
            "tokens_total": tokens_entrada + tokens_saida,
            "custo_usd": round(custo, 6),
            "modelo_mais_usado": mais_usado,
            "fallbacks": sum(1 for c in chamadas if c["fallback"]),
        },
        "serie_latencia": [
            {"hora": t["hora"], "latencia_ms": t["latencia_ms"]} for t in turnos
        ],
        "serie_custo": serie_custo,
        "por_modelo": por_modelo,
        "por_rota": por_rota,
        "turnos": [
            {**t, "custo_usd": round(t["custo_usd"], 6)} for t in turnos
        ],
    }


@router.get("/monitor")
def painel() -> dict:
    """Números do processo atual. Reiniciar o servidor zera o registro."""
    return montar_painel()
