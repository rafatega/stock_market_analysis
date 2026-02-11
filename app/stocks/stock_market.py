import streamlit as st
import pandas as pd
import yfinance as yf
import json
from pathlib import Path

# streamlit run app/stocks/stock_market.py

# Caminhos
BASE_DIR = Path("C:/Users/rafaeltegazzini/Documents/Projetos/stock_market_analysis")
JSON_PATH = BASE_DIR / "app/data/stock_market.json"

# Config Streamlit
st.set_page_config(page_title="Análise de Carteira", layout="wide")

# Carrega JSON
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

carteira_info = data["carteira"]
ativos = data["ativos"]

# Adiciona .SA se for BRL
for ativo in ativos:
    if ativo["moeda"] == "BRL" and not ativo["ticker"].endswith(".SA"):
        ativo["ticker"] += ".SA"

# DataFrame base
df = pd.DataFrame(ativos)

# Função para buscar preço atual
@st.cache_data(show_spinner=False, ttl=300)
def get_preco_atual(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        return None
    except Exception as e:
        return None

# Buscar preços
with st.spinner("Buscando preços atuais..."):
    df["preco_atual"] = df["ticker"].apply(get_preco_atual)

# Garantir tipos numéricos
df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce")
df["preco_medio"] = pd.to_numeric(df["preco_medio"], errors="coerce")
df["preco_atual"] = pd.to_numeric(df["preco_atual"], errors="coerce")

# Cálculos
df["valor_investido"] = (df["quantidade"] * df["preco_medio"]).round(2)
total_investido = df["valor_investido"].sum()
df["valor_atual"] = (df["quantidade"] * df["preco_atual"]).round(2)
total_atual = df["valor_atual"].sum()
df["lucro_prejuizo"] = (df["valor_atual"] - df["valor_investido"]).round(2)
df["rendimento_%"] = ((df["lucro_prejuizo"] / df["valor_investido"]) * 100).fillna(0).round(2)
df["participacao_%"] = ((df["valor_atual"] / total_atual) * 100).fillna(0).round(2)

# Sidebar
st.sidebar.header("Carteira")
st.sidebar.markdown(f"**Nome:** {carteira_info['nome']}")
st.sidebar.markdown(f"**Moeda base:** {carteira_info['moeda_base']}")
st.sidebar.markdown(f"**Data de atualização:** {carteira_info['data_atualizacao']}")

st.title("Análise de Carteira de Ações")

# ===== RESUMO GERAL =====
col1, col2, col3 = st.columns(3)

lucro_total = total_atual - total_investido
rendimento_total = (lucro_total / total_investido * 100) if total_investido > 0 else 0

with col1:
    st.metric("Total Investido", f"R$ {total_investido:,.2f}")
with col2:
    st.metric("Valor Atual", f"R$ {total_atual:,.2f}")
with col3:
    st.metric(
        "Rendimento Total",
        f"{rendimento_total:.2f}%",
        f"R$ {lucro_total:,.2f}"
    )

st.markdown("---")

# ===== TABELA POR ATIVO =====
st.subheader("Tabela por Ativo")

# MANTER OS DADOS NUMÉRICOS - não converter para string
df_display = df[[
    "ticker", "quantidade", "preco_medio", "preco_atual", 
    "valor_investido", "valor_atual", "lucro_prejuizo", 
    "rendimento_%", "participacao_%"
]].copy()

# Configuração de formatação das colunas
st.dataframe(
    df_display,
    use_container_width=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", width="small"),
        "quantidade": st.column_config.NumberColumn("Quantidade", format="%.0f"),
        "preco_medio": st.column_config.NumberColumn("Preço Médio", format="R$ %.2f"),
        "preco_atual": st.column_config.NumberColumn("Preço Atual", format="R$ %.2f"),
        "valor_investido": st.column_config.NumberColumn("Valor Investido", format="R$ %.2f"),
        "valor_atual": st.column_config.NumberColumn("Valor Atual", format="R$ %.2f"),
        "lucro_prejuizo": st.column_config.NumberColumn("Lucro/Prejuízo", format="R$ %.2f"),
        "rendimento_%": st.column_config.NumberColumn("Rendimento %", format="%.2f%%"),
        "participacao_%": st.column_config.NumberColumn("Participação %", format="%.2f%%"),
    }
)

st.markdown("---")

# ===== RESUMO POR SETOR =====
st.subheader("Resumo por Setor")

agrupado = df.groupby("setor", as_index=False).agg({
    "valor_investido": "sum",
    "valor_atual": "sum"
})

agrupado["lucro_prejuizo"] = (agrupado["valor_atual"] - agrupado["valor_investido"]).round(2)
agrupado["participacao_%"] = ((agrupado["valor_atual"] / total_atual) * 100).fillna(0).round(2)

# MANTER NUMÉRICO TAMBÉM
st.dataframe(
    agrupado,
    use_container_width=True,
    column_config={
        "setor": st.column_config.TextColumn("Setor"),
        "valor_investido": st.column_config.NumberColumn("Valor Investido", format="R$ %.2f"),
        "valor_atual": st.column_config.NumberColumn("Valor Atual", format="R$ %.2f"),
        "lucro_prejuizo": st.column_config.NumberColumn("Lucro/Prejuízo", format="R$ %.2f"),
        "participacao_%": st.column_config.NumberColumn("Participação %", format="%.2f%%"),
    }
)

# ===== GRÁFICO DE PIZZA =====
st.subheader("Distribuição por Setor")

import plotly.express as px

fig = px.pie(
    agrupado,
    values="valor_atual",
    names="setor",
    title="Participação por Setor",
    hole=0.3
)

fig.update_traces(textposition='inside', textinfo='percent+label')
st.plotly_chart(fig, use_container_width=True)