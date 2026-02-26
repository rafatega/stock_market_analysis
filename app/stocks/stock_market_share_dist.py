import streamlit as st
import pandas as pd
import yfinance as yf
import json
from pathlib import Path

# streamlit run app/stocks/stock_market_share_dist.py

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

# ===== REBALANCEAMENTO (METAS + APORTE) =====
st.markdown("---")
st.header("Rebalanceamento por Metas (aportes)")

st.caption(
    "Defina a meta de participação por ticker e o valor disponível (aporte). "
    "O cálculo considera o valor atual da carteira + aporte e sugere quantas ações comprar/vender."
)

# Segurança: remove linhas sem preço
df_reb = df.dropna(subset=["preco_atual"]).copy()

with st.expander("Configurações", expanded=True):
    aporte = st.number_input(
        "Valor disponível para investir (R$). Use negativo se quiser simular saque.",
        value=0.0,
        step=100.0,
        format="%.2f",
    )

    st.write("Metas de participação por ação (%):")

    # Meta default = participação atual (pra facilitar o primeiro uso)
    metas_base = pd.DataFrame({
        "ticker": df_reb["ticker"],
        "meta_%": df_reb["participacao_%"].fillna(0.0),
    }).reset_index(drop=True)

    # Editor de metas
    metas_edit = st.data_editor(
        metas_base,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker", disabled=True),
            "meta_%": st.column_config.NumberColumn("Meta %", min_value=0.0, max_value=100.0, step=0.1, format="%.2f"),
        },
        key="metas_tickers",
    )

# Normaliza metas (se não der 100%, a gente normaliza automaticamente)
metas_sum = float(metas_edit["meta_%"].sum())
if metas_sum <= 0:
    st.error("A soma das metas precisa ser maior que 0%.")
    st.stop()

metas_edit = metas_edit.copy()
metas_edit["meta_norm"] = metas_edit["meta_%"] / metas_sum  # soma = 1.0

# Junta metas no dataframe
df_reb = df_reb.merge(metas_edit[["ticker", "meta_%", "meta_norm"]], on="ticker", how="left")
df_reb["meta_%"] = df_reb["meta_%"].fillna(0.0)
df_reb["meta_norm"] = df_reb["meta_norm"].fillna(0.0)

# Total atual + aporte
total_pos_aporte = float(total_atual + aporte)

if total_pos_aporte <= 0:
    st.error("Total pós-aporte ficou <= 0. Ajuste o aporte ou revise a carteira.")
    st.stop()

# Valores alvo em R$
df_reb["valor_alvo"] = (df_reb["meta_norm"] * total_pos_aporte).round(2)

# Quanto falta/excede em R$
df_reb["delta_valor"] = (df_reb["valor_alvo"] - df_reb["valor_atual"]).round(2)

# Quantidade sugerida (inteira) - aproxima para o mais próximo
# Compra: arredonda para baixo se quiser ser conservador (não estourar caixa)
# Venda: arredonda para cima em magnitude (pra bater mais a meta)
import numpy as np

def sugerir_qtd(delta_valor: float, preco: float) -> int:
    if preco <= 0 or np.isnan(preco) or np.isnan(delta_valor):
        return 0
    qtd_float = delta_valor / preco
    if qtd_float >= 0:
        return int(np.floor(qtd_float))  # compra conservadora
    else:
        return int(np.ceil(qtd_float))   # venda conservadora (mais perto da meta)

df_reb["qtd_sugerida"] = df_reb.apply(lambda r: sugerir_qtd(r["delta_valor"], r["preco_atual"]), axis=1)

df_reb["acao"] = np.where(df_reb["qtd_sugerida"] > 0, "COMPRAR",
                   np.where(df_reb["qtd_sugerida"] < 0, "VENDER", "OK"))

df_reb["valor_estimado_ordem"] = (df_reb["qtd_sugerida"] * df_reb["preco_atual"]).round(2)

# Caixa usado (compras - vendas)
caixa_usado = float(df_reb["valor_estimado_ordem"].sum())
restante = float(aporte - caixa_usado)

# Carteira pós-ordens (estimada)
df_reb["quantidade_pos"] = (df_reb["quantidade"] + df_reb["qtd_sugerida"]).clip(lower=0)
df_reb["valor_pos"] = (df_reb["quantidade_pos"] * df_reb["preco_atual"]).round(2)
total_pos_estimado = float(df_reb["valor_pos"].sum() + restante)

df_reb["participacao_pos_%"] = ((df_reb["valor_pos"] / total_pos_estimado) * 100).fillna(0).round(2)

# KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total atual", f"R$ {total_atual:,.2f}")
c2.metric("Aporte", f"R$ {aporte:,.2f}")
c3.metric("Caixa usado (estim.)", f"R$ {caixa_usado:,.2f}")
c4.metric("Caixa restante (estim.)", f"R$ {restante:,.2f}")

# Tabela de sugestões
st.subheader("Sugestão de ordens para bater as metas")

df_ordens = df_reb[[
    "ticker", "preco_atual", "quantidade", "valor_atual",
    "meta_%", "valor_alvo", "delta_valor",
    "acao", "qtd_sugerida", "valor_estimado_ordem",
    "quantidade_pos", "valor_pos", "participacao_pos_%"
]].copy()

# Ordena: primeiro o que precisa agir
ordem_acao = {"COMPRAR": 0, "VENDER": 1, "OK": 2}
df_ordens["ordem"] = df_ordens["acao"].map(ordem_acao).fillna(9)
df_ordens = df_ordens.sort_values(["ordem", "ticker"]).drop(columns=["ordem"])

st.dataframe(
    df_ordens,
    use_container_width=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", width="small"),
        "preco_atual": st.column_config.NumberColumn("Preço Atual", format="R$ %.2f"),
        "quantidade": st.column_config.NumberColumn("Qtd Atual", format="%.0f"),
        "valor_atual": st.column_config.NumberColumn("Valor Atual", format="R$ %.2f"),
        "meta_%": st.column_config.NumberColumn("Meta %", format="%.2f%%"),
        "valor_alvo": st.column_config.NumberColumn("Valor Alvo", format="R$ %.2f"),
        "delta_valor": st.column_config.NumberColumn("Diferença (R$)", format="R$ %.2f"),
        "acao": st.column_config.TextColumn("Ação", width="small"),
        "qtd_sugerida": st.column_config.NumberColumn("Qtd (±)", format="%.0f"),
        "valor_estimado_ordem": st.column_config.NumberColumn("Valor Ordem (estim.)", format="R$ %.2f"),
        "quantidade_pos": st.column_config.NumberColumn("Qtd Pós", format="%.0f"),
        "valor_pos": st.column_config.NumberColumn("Valor Pós", format="R$ %.2f"),
        "participacao_pos_%": st.column_config.NumberColumn("Part. Pós %", format="%.2f%%"),
    }
)

# Avisos úteis
if abs(metas_sum - 100.0) > 0.01:
    st.info(f"As metas somavam {metas_sum:.2f}%. Eu normalizei automaticamente para 100%.")

if abs(restante) > 1e-6:
    st.caption("O 'caixa restante' aparece por causa do arredondamento para quantidade inteira de ações.")