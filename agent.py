# agent.py
# agent.py
import os
import sys
from datetime import datetime

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Adiciona o diretório atual ao path do Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data import carregar_dados
from prompt_agent import get_agent_prompt
from store_policies import STORE_POLICIES_TEXT
def initialize_system():
    """Inicializa os dados e exibe o status do agente de atendimento."""
    print("Initializing Artefact Customer Service Agent...")
    
    # 1. Carrega os dados dos CSVs
    data = carregar_dados()
    if data is None:
        print("Critical error loading data. Please check the Data folder.")
        return None
    
    products, orders, customers, categories, order_items, promotions = data
    
    print(f"-> Total products loaded: {len(products)}")
    print(f"-> Total orders loaded: {len(orders)}")
    
    # 2. Obtém o prompt e as políticas
    prompt = get_agent_prompt()
    print("-> Agent prompt successfully loaded and ready for use!")
    
    # 3. Inicializa o cliente da Anthropic (Modo Fallback ativado)
    # 3. Inicializa o cliente da Anthropic buscando do ambiente
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = None
    if api_key:
        client = Anthropic(api_key=api_key)
        print("-> Anthropic API Client initialized successfully!")
    else:
        print("-> Warning: ANTHROPIC_API_KEY not found in environment. Running in fallback/mock mode.")
    return products, orders, customers, categories, order_items, promotions, prompt, client

def lookup_order_details(order_id, orders_df, customers_df):
    """Busca os detalhes do pedido e calcula automaticamente se está dentro da janela de 7 dias."""
    try:
        order_row = orders_df[orders_df['order_id'].astype(str) == str(order_id)]
        
        if order_row.empty:
            return f"❌ Order ID '{order_id}' was not found in the database."
        
        order_info = order_row.iloc[0]
        customer_id = order_info.get('customer_id')
        order_status = order_info.get('status', 'Unknown')
        order_date_str = str(order_info.get('order_date', '')).split()[0]
        
        customer_name = "Customer"
        if customer_id and not customers_df.empty:
            customer_row = customers_df[customers_df['customer_id'].astype(str) == str(customer_id)]
            if not customer_row.empty:
                customer_name = customer_row.iloc[0].get('name', 'Customer')
        
        eligibility_msg = "Unable to calculate eligibility."
        try:
            order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
            current_date = datetime.now()
            delta_days = (current_date - order_date).days
            
            if order_status.lower() != "delivered":
                eligibility_msg = f"Order status is '{order_status}'. Returns are only applicable after delivery."
            elif delta_days <= 7:
                eligibility_msg = f"ELIGIBLE: Order was delivered {delta_days} day(s) ago (Within the 7-day return window)."
            else:
                eligibility_msg = f"NOT ELIGIBLE: Order was delivered {delta_days} days ago (Exceeds the 7-day return window)."
        except Exception as date_err:
            eligibility_msg = f"Date calculation error: {date_err}"

        summary = (
            f"Order ID: {order_id}\n"
            f"Customer Name: {customer_name}\n"
            f"Order Date: {order_date_str}\n"
            f"Status: {order_status}\n"
            f"Return Eligibility Status: {eligibility_msg}"
        )
        return summary

    except Exception as e:
        return f"Error looking up order details: {e}"

def lookup_product_details(query_text, products_df):
    """
    Retrieval Layer (RAG): Busca produtos no catálogo por correspondência 
    de palavras-chave no nome do produto.
    """
    try:
        if products_df.empty:
            return "No products database available."
        
        # Filtra palavras com mais de 2 letras para ignorar pontuações e artigos curtos
        words = [w.strip("?.,!#\"'").lower() for w in query_text.split() if len(w) > 2]
        
        # Palavras comuns de pergunta que devemos ignorar na busca de produto
        ignore_words = {"what", "when", "where", "which", "have", "sell", "does", "with", "from", "about", "this", "that", "para", "como", "sobre"}
        search_words = [w for w in words if w not in ignore_words]
        
        if not search_words:
            return None

        matches = pd.DataFrame()
        for word in search_words:
            # Busca case-insensitive no nome do produto
            found = products_df[products_df['name'].str.lower().str.contains(word, na=False)]
            if not found.empty:
                matches = pd.concat([matches, found]).drop_duplicates()
        
        if matches.empty:
            # Caso não encontre por palavra específica, retorna uma amostra de produtos para contexto
            return "No exact product title match found. (Tip: Try searching by main product keywords)."
        
        results = []
        for _, row in matches.head(5).iterrows(): # Retorna até 5 itens mais relevantes
            p_id = row.get('product_id', 'N/A')
            p_name = row.get('name', 'Unknown')
            p_price = row.get('price', 'N/A')
            p_cat = row.get('category_id', 'N/A')
            results.append(f"- Product ID {p_id}: {p_name} | Price: ${p_price} | Category ID: {p_cat}")
            
        return "✅ Catalog Product Matches Found:\n" + "\n".join(results)
    except Exception as e:
        return f"Error searching products catalog: {e}"
def generate_llm_response(client, system_prompt, policies, context_data, user_query):
    """Envia o contexto estruturado (Pedidos ou Produtos) para a IA gerar a resposta final."""
    if not client:
        return (
            f"[Fallback Mode - No API Key]\n"
            f"Retrieved Context:\n{context_data}\n\n"
            f"Query: {user_query}"
        )
    
    full_context = (
        f"=== STORE POLICIES ===\n{policies}\n\n"
        f"=== RETRIEVED DATABASE RECORD ===\n{context_data if context_data else 'No specific database record matched.'}\n\n"
        f"=== USER / SUPPORT QUERY ===\n{user_query}"
    )
    
    try:
        response = client.messages.create(
            model=os.getenv("MODEL_NAME", "claude-3-5-sonnet-20241024"),  # Modelo padrão estável
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": full_context}
            ]
        )

        text_blocks = [
            block.text for block in response.content if block.type == "text"
        ]
        if not text_blocks:
            return "Error communicating with Anthropic API: response contained no text block."
        return "\n".join(text_blocks)
    except Exception as e:
        return f"Error communicating with Anthropic API: {e}"

def run_interactive_agent(products, orders, customers, prompt, client):
    """Permite simular perguntas sobre pedidos ou produtos com IA integrada."""
    print("\n--------------------------------------------------")
    print("🤖 ARTEFACT FULL-STACK CLAUDE AGENT IS READY")
    print("Type your simulated customer/support question below.")
    print("Example 1: 'What is the status of order 2?'")
    print("Example 2: 'Do we sell any camera or lens products?'")
    print("Type 'exit' or 'quit' to close the session.")
    print("--------------------------------------------------")
    
    while True:
        try:
            user_query = input("\nSupport Representative Query: ").strip()
            if user_query.lower() in ["exit", "quit"]:
                print("Closing agent session. Good job!")
                break
            
            if not user_query:
                continue
            
            print("\n[Analyzing Query & Querying Pandas Databases...]")
            
            context_data = ""
            words = user_query.split()
            
            # 1. Verifica se é uma busca por ID de pedido (número puro)
            order_found = False
            for word in words:
                clean_word = word.strip("#,.?!")
                if clean_word.isdigit():
                    context_data = lookup_order_details(clean_word, orders, customers)
                    order_found = True
                    break
            
            # 2. Se não encontrou número de pedido, tenta buscar no catálogo de produtos
            if not order_found:
                context_data = lookup_product_details(user_query, products)
                if not context_data:
                    context_data = "No specific order ID or product match found in local CSV databases."
            
            # 3. Gera resposta final (via Claude ou Fallback)
            final_response = generate_llm_response(
                client, prompt, STORE_POLICIES_TEXT, context_data, user_query
            )
            
            print(f"\n🤖 Agent Response:\n{final_response}")
            
        except KeyboardInterrupt:
            print("\nSession interrupted. Exiting...")
            break

if __name__ == "__main__":
    system_data = initialize_system()
    if system_data:
        products, orders, customers, categories, order_items, promotions, prompt, client = system_data
        run_interactive_agent(products, orders, customers, prompt, client)