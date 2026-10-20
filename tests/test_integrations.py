import io
import json
import unittest
import uuid
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app import juiz
from app.observabilidade import (
    abrir_turno,
    coletor,
    custo_usd,
    fechar_turno,
    listar_chamadas,
    status_do_estado,
)
from app.routes.monitor import _percentil_95


class IntegrationTests(unittest.TestCase):
    def test_judge_uses_tool_evidence_and_keeps_supported_answer(self):
        state = {
            "messages": [
                HumanMessage(content="Quanto gastei?"),
                ToolMessage(content='{"amount": 30}', tool_call_id="call-1", name="query_transactions"),
                AIMessage(content="Você gastou 30."),
            ]
        }
        payload = {"answers": {"veredito": {"choice": "apoiada"}, "apoiada": {"noul": 0.9}}}
        response = io.BytesIO(json.dumps(payload).encode())
        with patch.object(juiz, "TYPESAFE_API_KEY", "test-key"), patch.object(
            juiz.urllib.request, "urlopen", return_value=response
        ) as send:
            result = juiz.no_juiz(state)

        request = send.call_args.args[0]
        submitted = json.loads(request.data)
        self.assertIn('"amount": 30', submitted["state"]["evidencia"])
        self.assertEqual(result.get("messages"), None)

    def test_monitor_math_and_blocked_status(self):
        self.assertEqual(_percentil_95([100, 300, 200]), 300)
        self.assertEqual(custo_usd("openai/gpt-oss-20b", 1_000_000, 1_000_000), 0.375)
        self.assertEqual(status_do_estado({"bloqueado": True}), "bloqueado")

    def test_model_call_is_attributed_to_its_turn(self):
        turn_id = abrir_turno()
        run_id = uuid.uuid4()
        coletor.on_chat_model_start(
            {"kwargs": {"model": "openai/gpt-oss-20b"}},
            [[]],
            run_id=run_id,
            metadata={"turno_id": turn_id, "langgraph_node": "roteador"},
        )
        result = LLMResult(generations=[[ChatGeneration(message=AIMessage(
            content="ok", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        ))]])
        coletor.on_llm_end(result, run_id=run_id)
        fechar_turno(turn_id, "roteador", "ok")

        call = listar_chamadas()[-1]
        self.assertEqual((call["tokens_entrada"], call["tokens_saida"]), (10, 5))
        self.assertEqual(call["no"], "roteador")

    def test_judge_replaces_unsupported_answer(self):
        state = {"messages": [HumanMessage(content="Qual o saldo?"), AIMessage(content="R$ 900")]}
        payload = {"answers": {"veredito": {"choice": "sem_apoio"}, "apoiada": {"noul": 0.1}}}
        with patch.object(juiz, "TYPESAFE_API_KEY", "test-key"), patch.object(
            juiz.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())
        ):
            result = juiz.no_juiz(state)
        self.assertEqual(result["messages"][0]["content"], juiz.FRASE_SEGURA)


if __name__ == "__main__":
    unittest.main()
