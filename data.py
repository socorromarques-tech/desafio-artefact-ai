# data.py
import os
import pandas as pd

# Caminho para a pasta Data dentro de Technical_challenge
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Technical_challenge", "Data")

def carregar_dados():
    """Carrega todos os arquivos CSV do desafio para análise."""
    try:
        products = pd.read_csv(os.path.join(DATA_DIR, "desafio_tecnico_ai_eng - products.csv"))
        orders = pd.read_csv(os.path.join(DATA_DIR, "desafio_tecnico_ai_eng - orders.csv"))
        customers = pd.read_csv(os.path.join(DATA_DIR, "desafio_tecnico_ai_eng - customers.csv"))
        categories = pd.read_csv(os.path.join(DATA_DIR, "desafio_tecnico_ai_eng - categories.csv"))
        order_items = pd.read_csv(os.path.join(DATA_DIR, "desafio_tecnico_ai_eng - order_items.csv"))
        promotions = pd.read_csv(os.path.join(DATA_DIR, "desafio_tecnico_ai_eng - promotions.csv"))
        
        print("All data successfully loaded!")
        return products, orders, customers, categories, order_items, promotions
    except Exception as e:
        print(f"Error loading files: {e}")
        return None

if __name__ == "__main__":
    carregar_dados()