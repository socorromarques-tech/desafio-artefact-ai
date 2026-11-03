import re
import unittest

from store_policies import get_policy_context, load_policy_pages


class StorePoliciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = load_policy_pages()

    def test_loads_policy_text_from_the_pdf(self):
        self.assertEqual(8, len(self.pages))
        self.assertIn("MANUAL DE", self.pages[0][1])

    def test_returns_policy_pages_relevant_to_the_topic(self):
        result = get_policy_context("devolução e troca", self.pages)

        self.assertIn("página 4", result)
        self.assertIn("7 (sete) dias corridos", result)

    def test_payment_question_returns_payment_rules(self):
        result = get_policy_context("formas de pagamento", self.pages)

        self.assertIn("PIX", result)
        self.assertIn("página 3", result)

    def test_address_question_returns_address_and_business_hours(self):
        result = get_policy_context("endereço e horário de funcionamento", self.pages)

        self.assertIn("Rua 14 de Maio", result)
        self.assertIn("09:00 às 18:00", result)

    def test_warranty_question_returns_legal_warranty_period(self):
        result = get_policy_context("garantia", self.pages)

        self.assertIn("90 (noventa) dias", result)

    def test_contact_question_exposes_conflicting_contacts_for_review(self):
        result = get_policy_context("contato da loja", self.pages)
        digits = re.sub(r"\D", "", result)

        self.assertIn("33414444", digits)
        self.assertIn("33214500", digits)

    def test_unknown_topic_does_not_invent_policy(self):
        result = get_policy_context("política de estacionamento", self.pages)

        self.assertIn("Não encontrei esse assunto", result)
        self.assertNotIn("7 (sete) dias corridos", result)

    def test_empty_topic_requests_a_subject(self):
        self.assertEqual(
            "Informe o assunto da política que deseja consultar.",
            get_policy_context("", self.pages),
        )


if __name__ == "__main__":
    unittest.main()
