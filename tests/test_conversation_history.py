import copy
import unittest
from types import SimpleNamespace

import pandas as pd

from agent import generate_llm_response


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        return self.responses.pop(0)


def text_response(text):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
    )


class ConversationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.dataframes = [pd.DataFrame() for _ in range(5)]

    def generate(self, client, query, history):
        return generate_llm_response(
            client,
            "system prompt",
            query,
            *self.dataframes,
            conversation_history=history,
        )

    def test_follow_up_question_receives_prior_user_and_assistant_messages(self):
        first_response = text_response("Encontrei dois violões.")
        messages = FakeMessages(
            [
                first_response,
                text_response("O segundo custa R$ 849,00."),
            ]
        )
        client = SimpleNamespace(messages=messages)
        history = []

        first_answer = self.generate(client, "Mostre violões.", history)
        second_answer = self.generate(client, "Quanto custa o segundo?", history)

        self.assertEqual("Encontrei dois violões.", first_answer)
        self.assertEqual("O segundo custa R$ 849,00.", second_answer)
        second_request = messages.requests[1]["messages"]
        self.assertEqual(
            [
                {"role": "user", "content": "Mostre violões."},
                {
                    "role": "assistant",
                    "content": first_response.content,
                },
                {"role": "user", "content": "Quanto custa o segundo?"},
            ],
            second_request,
        )

    def test_tool_calls_and_results_are_preserved_in_session_history(self):
        tool_use = SimpleNamespace(
            type="tool_use",
            id="tool-call-1",
            name="consultar_politicas",
            input={"tema": "pagamento"},
        )
        messages = FakeMessages(
            [
                SimpleNamespace(content=[tool_use]),
                text_response("Aceitamos PIX e cartão."),
                text_response("Como posso ajudar com o pagamento?"),
            ]
        )
        client = SimpleNamespace(messages=messages)
        history = []

        first_answer = self.generate(client, "Quais pagamentos aceitam?", history)
        second_answer = self.generate(client, "E o boleto?", history)

        self.assertEqual("Aceitamos PIX e cartão.", first_answer)
        self.assertEqual("Como posso ajudar com o pagamento?", second_answer)
        self.assertEqual(
            ["user", "assistant", "user", "assistant", "user", "assistant"],
            [message["role"] for message in history],
        )
        self.assertEqual("tool_result", history[2]["content"][0]["type"])
        self.assertEqual("tool-call-1", history[2]["content"][0]["tool_use_id"])
        self.assertEqual("Quais pagamentos aceitam?", messages.requests[0]["messages"][0]["content"])
        self.assertEqual(
            "E o boleto?",
            messages.requests[2]["messages"][-1]["content"],
        )
        self.assertEqual(
            "Quais pagamentos aceitam?",
            messages.requests[2]["messages"][0]["content"],
        )

    def test_history_is_not_changed_when_client_is_unavailable(self):
        history = [{"role": "user", "content": "pergunta anterior"}]

        result = self.generate(None, "pergunta nova", history)

        self.assertIn("sem conexão com a API", result)
        self.assertEqual(
            [{"role": "user", "content": "pergunta anterior"}],
            history,
        )


if __name__ == "__main__":
    unittest.main()
