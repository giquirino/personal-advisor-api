import io
import json
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app import juiz
from app import memory, prompts
from app.observabilidade import (
    _eh_fallback,
    abrir_turno,
    coletor,
    custo_usd,
    fechar_turno,
    listar_chamadas,
    status_do_estado,
)
from app.routes.monitor import _percentil_95
from app.tools import agenda


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

    def test_session_id_is_scoped_to_user(self):
        docs = {}
        collection = MagicMock()

        def find_one(query, *args, **kwargs):
            return next((doc for doc in docs.values() if all(
                doc.get(key) == value for key, value in query.items() if key != "resumo"
            )), None)

        def insert_one(doc):
            docs[doc["_id"]] = doc

        collection.find_one.side_effect = find_one
        collection.insert_one.side_effect = insert_one
        collection.update_one.side_effect = lambda query, update: docs[query["_id"]]["mensagens"].extend(
            update["$push"]["mensagens"]["$each"]
        )
        with patch.object(memory, "_get_col_sessoes", return_value=collection), patch.dict(
            memory._sessoes_ativas, {}, clear=True
        ):
            memory.salvar_mensagens("same-session", [{"role": "usuario", "content": "A"}], "user-a")
            memory.salvar_mensagens("same-session", [{"role": "usuario", "content": "B"}], "user-b")
        self.assertEqual(len(docs), 2)
        self.assertEqual({doc["user_id"]: doc["mensagens"][0]["content"] for doc in docs.values()},
                         {"user-a": "A", "user-b": "B"})

    def test_fallback_matches_the_primary_model_of_each_agent(self):
        self.assertFalse(_eh_fallback("financeiro", "openai/gpt-oss-20b"))
        self.assertTrue(_eh_fallback("agenda", "openai/gpt-oss-120b"))

    def test_calendar_compares_instants_across_time_zones(self):
        collection = MagicMock()
        collection.find.return_value = [{
            "_id": "existing", "inicio": "2026-10-20T10:00:00+00:00",
            "fim": "2026-10-20T11:00:00+00:00",
        }]
        config = {"configurable": {"user_id": "user-a"}}
        with patch.object(agenda, "_get_col_eventos", return_value=collection):
            invalid = agenda.criar_evento.func(
                "Meeting", "2026-10-20T10:00:00-03:00", "2026-10-20T12:00:00+00:00", config
            )
            conflict = agenda.criar_evento.func(
                "Meeting", "2026-10-20T07:30:00-03:00", "2026-10-20T08:30:00-03:00", config
            )
        self.assertEqual(invalid["status"], "error")
        self.assertEqual(conflict["status"], "conflict")
        collection.insert_one.assert_not_called()

    def test_prompt_time_is_generated_on_each_call(self):
        with patch.object(prompts, "datetime") as clock:
            clock.now.side_effect = [
                datetime(2026, 10, 20, tzinfo=timezone.utc),
                datetime(2026, 10, 21, tzinfo=timezone.utc),
            ]
            first, second = prompts.contexto_temporal(), prompts.contexto_temporal()
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
