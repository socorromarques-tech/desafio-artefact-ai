import unittest

from prompt_agent import get_agent_prompt


class AgentScopePromptTests(unittest.TestCase):
    def test_prompt_limits_responses_to_store_topics(self):
        prompt = get_agent_prompt()

        self.assertIn("Atenda somente assuntos da Empório da Música", prompt)
        self.assertIn("não responda com conhecimento geral", prompt)
        self.assertIn("Recuse com educação", prompt)

    def test_prompt_redirects_accessory_requests_using_store_policy(self):
        prompt = get_agent_prompt()

        self.assertIn("O catálogo da loja não inclui acessórios", prompt)
        self.assertIn("trabalha exclusivamente com instrumentos musicais", prompt)
        self.assertIn("consulte o manual de políticas", prompt)

    def test_prompt_contains_a_polite_out_of_scope_example(self):
        prompt = get_agent_prompt()

        self.assertIn("Desculpe, posso ajudar com instrumentos musicais", prompt)


if __name__ == "__main__":
    unittest.main()
