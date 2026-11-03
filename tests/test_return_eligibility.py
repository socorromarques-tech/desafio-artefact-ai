import os
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from agent import TOOLS, avaliar_prazo_devolucao, executar_ferramenta


class ReturnEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.order = pd.Series(
            {
                "status": "delivered",
                "purchase_channel": "online",
                "delivered_at": "2026-03-20",
                "estimated_delivery": "2026-03-25",
            }
        )

    def test_return_window_is_inclusive_through_seventh_calendar_day(self):
        result = avaliar_prazo_devolucao(
            self.order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("dentro do prazo de 7 dias corridos", result)
        self.assertIn("2026-03-27", result)

    def test_return_window_expires_after_seven_calendar_days(self):
        result = avaliar_prazo_devolucao(
            self.order, reference_date=date(2026, 3, 28)
        )

        self.assertIn("prazo de 7 dias corridos", result)
        self.assertIn("ultrapassado", result)
        self.assertIn("não avalia outros direitos", result)

    def test_estimated_delivery_is_not_used_as_actual_receipt_date(self):
        order = self.order.drop(labels=["delivered_at"])

        result = avaliar_prazo_devolucao(
            order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("data real de recebimento", result)
        self.assertIn("previsão de entrega não a substitui", result)

    def test_missing_purchase_channel_does_not_assume_online_purchase(self):
        order = self.order.drop(labels=["purchase_channel"])

        result = avaliar_prazo_devolucao(
            order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("canal da compra", result)

    def test_non_online_purchase_is_not_assessed_under_online_right(self):
        order = self.order.copy()
        order["purchase_channel"] = "presencial"

        result = avaliar_prazo_devolucao(
            order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("não está registrado como compra online", result)

    def test_undelivered_order_is_not_assessed(self):
        order = self.order.copy()
        order["status"] = "shipped"

        result = avaliar_prazo_devolucao(
            order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("não está marcado como entregue", result)

    def test_future_receipt_date_is_reported_as_inconsistent(self):
        result = avaliar_prazo_devolucao(
            self.order, reference_date=date(2026, 3, 19)
        )

        self.assertIn("posterior à data de referência", result)

    def test_invalid_receipt_date_is_not_assessed(self):
        order = self.order.copy()
        order["delivered_at"] = "data inválida"

        result = avaliar_prazo_devolucao(
            order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("data real de recebimento é inválida", result)

    def test_reference_date_can_be_configured_for_reproducible_demos(self):
        with patch.dict(os.environ, {"REFERENCE_DATE": "2026-03-27"}):
            result = avaliar_prazo_devolucao(self.order)

        self.assertIn("2026-03-27 como data de referência", result)

    def test_invalid_configured_reference_date_raises_an_error(self):
        with patch.dict(os.environ, {"REFERENCE_DATE": "27/03/2026"}):
            with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                avaliar_prazo_devolucao(self.order)

    def test_actual_orders_without_receipt_metadata_are_not_misclassified(self):
        from data import carregar_dados

        _, orders, _, _, _, _ = carregar_dados()
        delivered_order = orders[orders["status"].eq("delivered")].iloc[0]

        result = avaliar_prazo_devolucao(
            delivered_order, reference_date=date(2026, 3, 27)
        )

        self.assertIn("data real de recebimento", result)
        self.assertIn("canal da compra", result)
        self.assertNotIn("ultrapassado", result)
        self.assertNotIn("dentro do prazo", result)

    def test_return_tool_requires_identity_before_assessing_order(self):
        from data import carregar_dados

        _, orders, customers, categories, _, promotions = carregar_dados()
        order_id = str(orders.iloc[0]["order_id"])
        result = executar_ferramenta(
            "verificar_prazo_devolucao",
            {"order_id": order_id},
            pd.DataFrame(),
            orders,
            customers,
            categories,
            promotions,
        )

        self.assertIn("solicite o e-mail ou telefone", result)

    def test_authenticated_live_order_reports_missing_delivery_evidence(self):
        from data import carregar_dados

        _, orders, customers, categories, _, promotions = carregar_dados()
        order = orders.iloc[0]
        customer = customers[
            customers["customer_id"].astype(str).eq(str(order["customer_id"]))
        ].iloc[0]
        result = executar_ferramenta(
            "verificar_prazo_devolucao",
            {
                "order_id": str(order["order_id"]),
                "contato_cliente": str(customer["email"]),
            },
            pd.DataFrame(),
            orders,
            customers,
            categories,
            promotions,
        )

        self.assertIn("data real de recebimento", result)
        self.assertIn("canal da compra", result)
        self.assertNotIn("ultrapassado", result)
        self.assertNotIn("dentro do prazo", result)

    def test_return_tool_is_available_to_the_model(self):
        return_tool_names = {tool["name"] for tool in TOOLS}

        self.assertIn("verificar_prazo_devolucao", return_tool_names)


if __name__ == "__main__":
    unittest.main()
