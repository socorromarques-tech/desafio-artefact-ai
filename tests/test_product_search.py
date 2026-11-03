import unittest

import pandas as pd

from agent import buscar_produtos


class BuscarProdutosTests(unittest.TestCase):
    def setUp(self):
        self.products = pd.DataFrame(
            [
                {
                    "product_id": 1,
                    "name": "Violão Árvore Nylon",
                    "price_brl": 599.9,
                    "category_id": 1,
                    "description": "Instrumento acústico para iniciantes",
                    "stock_quantity": 3,
                    "status": "active",
                },
                {
                    "product_id": 2,
                    "name": "Guitarra Elétrica",
                    "price_brl": 1200,
                    "category_id": 2,
                    "description": "Guitarra de corpo sólido",
                    "stock_quantity": 0,
                    "status": "active",
                },
                {
                    "product_id": 3,
                    "name": "Violão Descontinuado",
                    "price_brl": 400,
                    "category_id": 1,
                    "description": "Instrumento fora de catálogo",
                    "stock_quantity": 5,
                    "status": "inactive",
                },
            ]
        )
        self.categories = pd.DataFrame(
            [
                {"category_id": 1, "name": "Violões"},
                {"category_id": 2, "name": "Guitarras"},
            ]
        )
        self.promotions = pd.DataFrame(
            [
                {
                    "product_id": 1,
                    "discount_percent": 10,
                    "is_active": 1,
                },
                {
                    "product_id": 2,
                    "discount_percent": 20,
                    "is_active": 0,
                },
            ]
        )

    def search(self, **filters):
        return buscar_produtos(
            self.products,
            self.categories,
            self.promotions,
            **filters,
        )

    def test_search_is_case_and_accent_insensitive(self):
        result = self.search(termo="violao arvore")

        self.assertIn("Violão Árvore Nylon", result)
        self.assertNotIn("Violão Descontinuado", result)

    def test_category_can_be_selected_by_name_or_id(self):
        by_name = self.search(categoria="VIOLÕES")
        by_id = self.search(categoria="1")

        self.assertIn("Violão Árvore Nylon", by_name)
        self.assertNotIn("Guitarra Elétrica", by_name)
        self.assertIn("Violão Árvore Nylon", by_id)
        self.assertNotIn("Guitarra Elétrica", by_id)

    def test_maximum_price_filters_products(self):
        result = self.search(preco_maximo=700)

        self.assertIn("Violão Árvore Nylon", result)
        self.assertNotIn("Guitarra Elétrica", result)

    def test_stock_filter_excludes_unavailable_products(self):
        result = self.search(termo="guitarra", somente_com_estoque=True)

        self.assertIn("Nenhum instrumento encontrado", result)

    def test_prices_are_formatted_in_brazilian_currency(self):
        result = self.search(termo="violao arvore")

        self.assertIn("Preço: R$ 599,90", result)

    def test_active_promotion_includes_discount_and_promotional_price(self):
        result = self.search(termo="violao arvore")

        self.assertIn("Promoção ativa: 10% de desconto", result)
        self.assertIn("preço promocional R$ 539,91", result)

    def test_inactive_promotion_is_not_applied(self):
        result = self.search(termo="guitarra")

        self.assertNotIn("Promoção ativa", result)

    def test_unknown_category_and_unmatched_term_return_clear_messages(self):
        unknown_category = self.search(categoria="Pianos")
        unmatched_term = self.search(termo="produto inexistente")

        self.assertEqual("Não encontrei essa categoria no catálogo.", unknown_category)
        self.assertEqual(
            "Nenhum instrumento encontrado com esses critérios.",
            unmatched_term,
        )

    def test_empty_catalog_returns_clear_message(self):
        result = buscar_produtos(
            self.products.iloc[0:0],
            self.categories,
            self.promotions,
        )

        self.assertEqual("O catálogo de produtos está vazio.", result)


if __name__ == "__main__":
    unittest.main()
