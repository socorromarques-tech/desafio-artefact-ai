import os
import re
import unicodedata
from datetime import date

import anthropic
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from data import carregar_dados
from prompt_agent import get_agent_prompt
from store_policies import get_policy_context, load_policy_pages


MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-5-5")
MAX_TOOL_TURNS = 5

TOOLS = [
    {
        "name": "buscar_produtos",
        "description": (
            "Busca instrumentos no catálogo. Use esta ferramenta antes de responder "
            "sobre produtos, preços, categorias ou disponibilidade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {
                    "type": "string",
                    "description": "Termo curto para buscar no nome ou descrição do instrumento.",
                },
                "categoria": {
                    "type": "string",
                    "description": "Nome ou ID da categoria, se o cliente indicar uma.",
                },
                "preco_maximo": {
                    "type": "number",
                    "description": "Preço máximo em reais, se o cliente indicar um limite.",
                },
                "somente_com_estoque": {
                    "type": "boolean",
                    "description": "Defina como true se o cliente pedir itens disponíveis agora.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "consultar_pedido",
        "description": (
            "Consulta um pedido. É obrigatório confirmar o e-mail ou telefone associado "
            "ao pedido antes de revelar qualquer detalhe."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Identificador do pedido informado pelo cliente.",
                },
                "contato_cliente": {
                    "type": "string",
                    "description": (
                        "E-mail ou telefone informado pelo cliente para verificar "
                        "que é o titular do pedido. Nunca invente esse dado."
                    ),
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "verificar_prazo_devolucao",
        "description": (
            "Verifica o prazo de arrependimento para uma compra online usando a data "
            "real de recebimento do pedido. É obrigatório confirmar o e-mail ou telefone "
            "associado ao pedido. Nunca use a previsão de entrega como data de recebimento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Identificador do pedido informado pelo cliente.",
                },
                "contato_cliente": {
                    "type": "string",
                    "description": (
                        "E-mail ou telefone informado pelo cliente para verificar "
                        "que é o titular do pedido."
                    ),
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "consultar_politicas",
        "description": (
            "Consulta as políticas oficiais disponíveis. Use antes de responder "
            "sobre devolução, troca, entrega, pagamento ou garantia."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tema": {
                    "type": "string",
                    "description": "Assunto da política que o cliente quer conhecer.",
                }
            },
            "required": ["tema"],
        },
    },
]


def initialize_system():
    """Carrega dados, prompt e cliente opcional da Anthropic."""
    print("Iniciando o agente de atendimento...")

    data = carregar_dados()
    if data is None:
        print("Erro ao carregar os dados. Confira os arquivos da pasta data/.")
        return None

    try:
        policy_pages = load_policy_pages()
    except (OSError, ValueError) as error:
        print(f"Erro ao carregar o manual de políticas: {error}")
        return None

    try:
        _get_reference_date()
    except ValueError as error:
        print(f"Erro na configuração de data de referência: {error}")
        return None

    products, orders, customers, categories, order_items, promotions = data
    print(f"-> {len(products)} produtos carregados")
    print(f"-> {len(orders)} pedidos carregados")
    print(f"-> Manual de políticas carregado ({len(policy_pages)} páginas com texto)")

    prompt = get_agent_prompt()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    client = None
    if api_key and api_key != "your_anthropic_api_key_here":
        client = anthropic.Anthropic(api_key=api_key)
        print("-> Cliente da Anthropic inicializado")
    else:
        print("-> ANTHROPIC_API_KEY ausente; modo sem API ativado")

    return products, orders, customers, categories, order_items, promotions, prompt, client


def _normalize_text(value):
    normalized = unicodedata.normalize("NFD", str(value))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn").casefold()


def _format_brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _get_reference_date(reference_date=None):
    if reference_date is not None:
        return reference_date

    configured_date = os.getenv("REFERENCE_DATE", "").strip()
    if configured_date:
        try:
            return date.fromisoformat(configured_date)
        except ValueError as error:
            raise ValueError(
                "REFERENCE_DATE deve estar no formato YYYY-MM-DD."
            ) from error
    return date.today()


def _get_verified_order(order_id, contact, orders_df, customers_df):
    if not contact or not str(contact).strip():
        return None, (
            "Para proteger os dados do cliente, solicite o e-mail ou telefone "
            "associado ao pedido antes de consultá-lo."
        )

    matching_orders = orders_df[
        orders_df["order_id"].astype(str).eq(str(order_id))
    ]
    if matching_orders.empty:
        return None, "Não foi possível confirmar o pedido com os dados informados."

    order = matching_orders.iloc[0]
    customers = customers_df[
        customers_df["customer_id"].astype(str).eq(str(order["customer_id"]))
    ]
    if customers.empty:
        return None, "Não foi possível confirmar o pedido com os dados informados."

    customer = customers.iloc[0]
    normalized_contact = str(contact).strip()
    email_matches = (
        "@" in normalized_contact
        and _normalize_text(normalized_contact)
        == _normalize_text(customer.get("email", ""))
    )
    phone_matches = (
        "@" not in normalized_contact
        and re.sub(r"\D", "", normalized_contact)
        == re.sub(r"\D", "", str(customer.get("phone", "")))
    )
    if not (email_matches or phone_matches):
        return None, "Não foi possível confirmar o pedido com os dados informados."
    return order, None


def avaliar_prazo_devolucao(order, reference_date=None):
    """Avalia somente o prazo de arrependimento, sem presumir data ou canal."""
    order_status = _normalize_text(order.get("status", ""))
    if order_status != "delivered":
        return (
            "Ainda não é possível avaliar o prazo de devolução: o pedido não está "
            "marcado como entregue."
        )

    received_at = next(
        (
            order.get(column)
            for column in ("received_at", "delivered_at", "actual_delivery_date")
            if order.get(column) is not None and str(order.get(column)).strip()
        ),
        None,
    )
    channel_value = order.get("purchase_channel", order.get("channel", ""))
    channel = re.sub(r"[\W_]+", " ", _normalize_text(channel_value)).strip()

    missing_facts = []
    if received_at is None or pd.isna(received_at):
        missing_facts.append(
            "a data real de recebimento (a previsão de entrega não a substitui)"
        )
    if not channel:
        missing_facts.append("o canal da compra")
    if missing_facts:
        return (
            "Não é possível calcular o prazo: faltam "
            + " e ".join(missing_facts)
            + " nos dados do pedido."
        )

    delivery_timestamp = pd.to_datetime(received_at, errors="coerce")
    if pd.isna(delivery_timestamp):
        return "Não é possível calcular o prazo: a data real de recebimento é inválida."

    online_channels = {
        "online",
        "ecommerce",
        "e commerce",
        "online store",
        "site",
        "loja virtual",
        "compra online",
    }
    if channel not in online_channels:
        return (
            "O manual define o direito de arrependimento de 7 dias para compras "
            "online, mas este pedido não está registrado como compra online. "
            "Consulte a política de trocas para avaliar outras condições."
        )

    delivery_date = delivery_timestamp.date()
    evaluation_date = _get_reference_date(reference_date)
    if delivery_date > evaluation_date:
        return (
            f"A data real de recebimento ({delivery_date.isoformat()}) é posterior "
            f"à data de referência ({evaluation_date.isoformat()}); confira os dados."
        )

    elapsed_days = (evaluation_date - delivery_date).days
    if elapsed_days <= 7:
        return (
            f"O pedido foi recebido em {delivery_date.isoformat()}, há {elapsed_days} "
            f"dias, considerando {evaluation_date.isoformat()} como data de referência. "
            "Está dentro do prazo de 7 dias corridos do direito de arrependimento. "
            "A solicitação ainda depende das condições do manual, incluindo produto "
            "sem sinais de uso, embalagem original, acessórios e manuais."
        )

    return (
        f"O pedido foi recebido em {delivery_date.isoformat()}, há {elapsed_days} "
        f"dias, considerando {evaluation_date.isoformat()} como data de referência. "
        "O prazo de 7 dias corridos do direito de arrependimento descrito no manual "
        "foi ultrapassado. Isso não avalia outros direitos de troca ou garantia."
    )


def buscar_produtos(
    products_df,
    categories_df,
    promotions_df,
    termo="",
    categoria="",
    preco_maximo=None,
    somente_com_estoque=False,
):
    """Retorna itens do catálogo que correspondem aos filtros estruturados."""
    if products_df.empty:
        return "O catálogo de produtos está vazio."

    matches = products_df.copy()
    if "status" in matches:
        matches = matches[
            matches["status"].astype(str).str.casefold().eq("active")
        ]

    if termo:
        query_terms = _normalize_text(termo).split()
        searchable = (
            matches["name"].fillna("").astype(str)
            + " "
            + matches["description"].fillna("").astype(str)
        ).map(_normalize_text)
        matches = matches[
            searchable.map(lambda text: all(term in text for term in query_terms))
        ]

    if categoria:
        normalized_category = _normalize_text(categoria)
        category_ids = categories_df["category_id"].astype(str)
        category_names = categories_df["name"].fillna("").astype(str).map(_normalize_text)
        category_matches = categories_df[
            category_ids.eq(str(categoria))
            | category_names.eq(normalized_category)
            | category_names.str.contains(re.escape(normalized_category), na=False)
        ]
        if category_matches.empty:
            return "Não encontrei essa categoria no catálogo."
        matches = matches[
            matches["category_id"].astype(str).isin(
                category_matches["category_id"].astype(str)
            )
        ]

    prices = pd.to_numeric(matches["price_brl"], errors="coerce")
    if preco_maximo is not None:
        matches = matches[prices <= float(preco_maximo)]
        prices = pd.to_numeric(matches["price_brl"], errors="coerce")

    stock = pd.to_numeric(matches["stock_quantity"], errors="coerce").fillna(0)
    if somente_com_estoque:
        matches = matches[stock > 0]
        prices = pd.to_numeric(matches["price_brl"], errors="coerce")
        stock = pd.to_numeric(matches["stock_quantity"], errors="coerce").fillna(0)

    if matches.empty:
        return "Nenhum instrumento encontrado com esses critérios."

    category_names_by_id = dict(
        zip(categories_df["category_id"].astype(str), categories_df["name"].astype(str))
    )
    active_promotions = {}
    if not promotions_df.empty:
        active = promotions_df["is_active"].astype(str).str.strip().str.casefold().isin(
            {"1", "true", "yes", "sim"}
        )
        for _, promotion in promotions_df[active].iterrows():
            product_id = str(promotion["product_id"])
            discount = pd.to_numeric(
                pd.Series([promotion["discount_percent"]]), errors="coerce"
            ).iloc[0]
            if pd.notna(discount) and 0 < discount <= 100:
                active_promotions[product_id] = max(
                    active_promotions.get(product_id, 0), float(discount)
                )

    results = []
    for _, product in matches.head(10).iterrows():
        product_id = str(product["product_id"])
        price = float(product["price_brl"])
        stock_value = pd.to_numeric(
            pd.Series([product["stock_quantity"]]), errors="coerce"
        ).iloc[0]
        stock_quantity = 0 if pd.isna(stock_value) else int(stock_value)
        category_name = category_names_by_id.get(str(product["category_id"]), "Sem categoria")
        line = (
            f"- {product['name']} | Categoria: {category_name} | "
            f"Preço: {_format_brl(price)} | Estoque: {stock_quantity}"
        )
        discount = active_promotions.get(product_id)
        if discount:
            line += (
                f" | Promoção ativa: {discount:g}% de desconto "
                f"(preço promocional {_format_brl(price * (1 - discount / 100))})"
            )
        results.append(line)

    return "\n".join(results)


def consultar_pedido(order_id, contato_cliente, orders_df, customers_df):
    """Consulta pedido somente após verificar o e-mail ou telefone do titular."""
    order, error = _get_verified_order(
        order_id, contato_cliente, orders_df, customers_df
    )
    if error:
        return error

    total = pd.to_numeric(pd.Series([order.get("total_brl")]), errors="coerce").iloc[0]
    summary = [
        f"Pedido: {order_id}",
        f"Status: {order.get('status', 'não informado')}",
    ]
    if pd.notna(total):
        summary.append(f"Total: {_format_brl(float(total))}")
    for label, column in (
        ("Data do pedido", "order_date"),
        ("Previsão de entrega", "estimated_delivery"),
        ("Código de rastreamento", "tracking_code"),
    ):
        value = order.get(column)
        if pd.notna(value) and str(value).strip():
            summary.append(f"{label}: {value}")
    return "\n".join(summary)


def executar_ferramenta(
    name,
    tool_input,
    products_df,
    orders_df,
    customers_df,
    categories_df,
    promotions_df,
):
    """Executa uma ferramenta solicitada pelo modelo."""
    if name == "buscar_produtos":
        return buscar_produtos(
            products_df,
            categories_df,
            promotions_df,
            termo=tool_input.get("termo", ""),
            categoria=tool_input.get("categoria", ""),
            preco_maximo=tool_input.get("preco_maximo"),
            somente_com_estoque=tool_input.get("somente_com_estoque", False),
        )
    if name == "consultar_pedido":
        return consultar_pedido(
            tool_input.get("order_id", ""),
            tool_input.get("contato_cliente", ""),
            orders_df,
            customers_df,
        )
    if name == "verificar_prazo_devolucao":
        order, error = _get_verified_order(
            tool_input.get("order_id", ""),
            tool_input.get("contato_cliente", ""),
            orders_df,
            customers_df,
        )
        if error:
            return error
        return avaliar_prazo_devolucao(order)
    if name == "consultar_politicas":
        return get_policy_context(tool_input.get("tema", ""))
    raise ValueError(f"Ferramenta desconhecida solicitada pelo modelo: {name}")


def generate_llm_response(
    client,
    system_prompt,
    user_query,
    products_df,
    orders_df,
    customers_df,
    categories_df,
    promotions_df,
    conversation_history=None,
):
    """Responde usando ferramentas e, opcionalmente, o histórico da sessão."""
    if client is None:
        return (
            "O agente está sem conexão com a API e não pode selecionar ferramentas. "
            "Configure ANTHROPIC_API_KEY para consultar produtos, pedidos e políticas."
        )

    messages = list(conversation_history or [])
    messages.append({"role": "user", "content": user_query})
    for _ in range(MAX_TOOL_TURNS):
        try:
            response = client.messages.create(
                model=os.getenv("MODEL_NAME", MODEL_NAME),
                max_tokens=1200,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError as error:
            return f"Falha ao consultar a API da Anthropic: {error}"

        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        tool_calls = [
            block
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
        ]

        if not tool_calls:
            if text_blocks:
                messages.append(
                    {"role": "assistant", "content": response.content}
                )
                if conversation_history is not None:
                    conversation_history[:] = messages
                return "\n".join(text_blocks)
            return "A API não retornou uma resposta em texto."

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tool_call in tool_calls:
            result = executar_ferramenta(
                tool_call.name,
                tool_call.input,
                products_df,
                orders_df,
                customers_df,
                categories_df,
                promotions_df,
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "A consulta excedeu o limite de chamadas de ferramentas. Tente novamente."


def run_interactive_agent(
    products,
    orders,
    customers,
    categories,
    promotions,
    prompt,
    client,
):
    """Executa uma sessão interativa de atendimento ao cliente."""
    print("\nAgente de atendimento da Empório da Música")
    print("Exemplos: 'violões até R$ 1.000' ou 'qual é a política de devolução?'")
    print("Digite 'sair' para encerrar.")

    conversation_history = []
    while True:
        try:
            user_query = input("\nCliente: ").strip()
            if user_query.casefold() in {"sair", "exit", "quit"}:
                print("Atendimento encerrado.")
                break
            if not user_query:
                continue

            response = generate_llm_response(
                client,
                prompt,
                user_query,
                products,
                orders,
                customers,
                categories,
                promotions,
                conversation_history,
            )
            print(f"\nEmpório da Música: {response}")
        except KeyboardInterrupt:
            print("\nAtendimento interrompido.")
            break


if __name__ == "__main__":
    system_data = initialize_system()
    if system_data:
        (
            products,
            orders,
            customers,
            categories,
            _order_items,
            promotions,
            prompt,
            client,
        ) = system_data
        run_interactive_agent(
            products, orders, customers, categories, promotions, prompt, client
        )
