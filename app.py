import io
import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px


# ----------------------------
# Config
# ----------------------------
st.set_page_config(
    page_title="IBEM | Dashboard Financeiro",
    page_icon="📊",
    layout="wide",
)

st.title("📊 IBEM — Dashboard Financeiro")
st.caption("Upload do CSV → filtros → KPIs → gráficos → tabela → exportação")


# ----------------------------
# Helpers
# ----------------------------
def brl_format(x: float) -> str:
    # Formata 1234.56 -> R$ 1.234,56
    try:
        s = f"{x:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return "R$ 0,00"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return None


def parse_money_series(s: pd.Series) -> pd.Series:
    """
    Aceita:
    - 50.0
    - "R$ 50,00"
    - "50,00"
    - "1.234,56"
    - "1234.56"
    Retorna float
    """
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")

    def _to_float(v):
        if pd.isna(v):
            return np.nan
        txt = str(v).strip()

        # remove moeda e espaços
        txt = re.sub(r"[Rr]\$|\s", "", txt)

        # se tiver . e , no padrão pt-BR: 1.234,56
        if re.match(r"^\d{1,3}(\.\d{3})+,\d{2}$", txt):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            # se tiver vírgula, assume decimal
            if "," in txt and "." not in txt:
                txt = txt.replace(",", ".")
            # se tiver múltiplos pontos, remove separadores
            if txt.count(".") > 1:
                parts = txt.split(".")
                txt = "".join(parts[:-1]) + "." + parts[-1]

        try:
            return float(txt)
        except Exception:
            return np.nan

    return s.map(_to_float)


def ensure_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Se houver coluna de data, usa.
    Se não houver, cria 'data_lancamento' vazia e usa índice como referência.
    """
    df = df.copy()

    date_col = find_column(df, ["data", "data_lancamento", "dt", "competencia"])
    if date_col:
        df["data_lancamento"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    else:
        df["data_lancamento"] = pd.NaT

    # Criar ano/mes para gráficos, mesmo sem data (fica NaN)
    df["ano"] = df["data_lancamento"].dt.year
    df["mes"] = df["data_lancamento"].dt.month
    df["ano_mes"] = df["data_lancamento"].dt.to_period("M").astype(str)

    return df


# ----------------------------
# Sidebar: Upload + controles
# ----------------------------
with st.sidebar:
    st.header("⚙️ Controles")
    up = st.file_uploader("Envie seu CSV limpo", type=["csv"])

    st.divider()
    st.markdown("**Dica:** seu CSV ideal tem colunas como:")
    st.code("numero_lancamento, fornecedor_funcionario, valor_pago", language="text")

    st.divider()
    st.markdown("**Preferências**")
    top_n = st.slider("Top N (Ranking)", 5, 50, 20)
    show_raw = st.toggle("Mostrar tabela completa", value=True)


if not up:
    st.info("📌 Envie um arquivo CSV para começar.")
    st.stop()


# ----------------------------
# Load CSV
# ----------------------------
try:
    # tenta ; e , automaticamente
    content = up.getvalue()
    try:
        df = pd.read_csv(io.BytesIO(content), sep=",", encoding="utf-8-sig")
        if df.shape[1] == 1:
            df = pd.read_csv(io.BytesIO(content), sep=";", encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(io.BytesIO(content), sep=";", encoding="utf-8-sig")
except Exception as e:
    st.error(f"Não consegui ler o CSV. Detalhe: {e}")
    st.stop()

df = normalize_columns(df)

# Detectar colunas principais (flexível)
col_num = find_column(df, ["numero_lancamento", "n_lanc", "num", "numero"])
col_nome = find_column(df, ["fornecedor_funcionario", "fornecedor", "funcionario", "nome", "beneficiario"])
col_valor = find_column(df, ["valor_pago", "valor", "pago", "valor_total"])

if not col_nome or not col_valor:
    st.error(
        "Seu CSV precisa ter pelo menos: (nome do fornecedor/funcionário) e (valor pago).\n\n"
        "Exemplo: fornecedor_funcionario, valor_pago"
    )
    st.write("Colunas encontradas:", list(df.columns))
    st.stop()

# Limpeza de valores
df["fornecedor_funcionario"] = df[col_nome].astype(str).str.strip()
df["valor_pago"] = parse_money_series(df[col_valor])

if col_num:
    df["numero_lancamento"] = df[col_num].astype(str).str.strip()
else:
    df["numero_lancamento"] = ""

df = ensure_date_column(df)

# Remover linhas inválidas
df = df.dropna(subset=["valor_pago"])
df = df[df["valor_pago"] != 0]

# ----------------------------
# Filtros
# ----------------------------
st.subheader("🔎 Filtros")

c1, c2, c3 = st.columns([2, 1, 1])

with c1:
    search = st.text_input("Buscar por fornecedor/funcionário", value="", placeholder="Ex: PAULO, BELA, INTERNET...")
with c2:
    vmin, vmax = st.slider(
        "Faixa de valor (R$)",
        float(df["valor_pago"].min()),
        float(df["valor_pago"].max()),
        (float(df["valor_pago"].min()), float(df["valor_pago"].max())),
    )
with c3:
    # filtro de mês só se houver datas
    has_dates = df["data_lancamento"].notna().any()
    if has_dates:
        meses = ["(Todos)"] + sorted(df["ano_mes"].dropna().unique().tolist())
        sel_mes = st.selectbox("Competência (Ano-Mês)", meses, index=0)
    else:
        sel_mes = "(Sem datas no CSV)"
        st.selectbox("Competência (Ano-Mês)", [sel_mes], disabled=True)

filtered = df.copy()
if search.strip():
    filtered = filtered[filtered["fornecedor_funcionario"].str.contains(search, case=False, na=False)]
filtered = filtered[(filtered["valor_pago"] >= vmin) & (filtered["valor_pago"] <= vmax)]
if has_dates and sel_mes != "(Todos)":
    filtered = filtered[filtered["ano_mes"] == sel_mes]

# ----------------------------
# KPIs
# ----------------------------
st.divider()
k1, k2, k3, k4 = st.columns(4)

total_pago = float(filtered["valor_pago"].sum())
qtd_lanc = int(len(filtered))
qtd_pessoas = int(filtered["fornecedor_funcionario"].nunique())
ticket_medio = float(filtered["valor_pago"].mean()) if qtd_lanc else 0.0

k1.metric("💰 Total pago", brl_format(total_pago))
k2.metric("🧾 Lançamentos", f"{qtd_lanc:,}".replace(",", "."))
k3.metric("👥 Pessoas únicas", f"{qtd_pessoas:,}".replace(",", "."))
k4.metric("📉 Ticket médio", brl_format(ticket_medio))

# ----------------------------
# Charts
# ----------------------------
st.divider()
left, right = st.columns([1.1, 0.9])

# Top N
rank = (
    filtered.groupby("fornecedor_funcionario", as_index=False)["valor_pago"]
    .sum()
    .sort_values("valor_pago", ascending=False)
    .head(top_n)
)

with left:
    st.subheader(f"📌 Top {top_n} — Quem mais recebeu")
    fig = px.bar(
        rank,
        x="valor_pago",
        y="fornecedor_funcionario",
        orientation="h",
        title="Total pago por fornecedor/funcionário",
    )
    fig.update_layout(height=520, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("📈 Evolução por mês")
    if has_dates:
        serie = (
            filtered.dropna(subset=["data_lancamento"])
            .groupby("ano_mes", as_index=False)["valor_pago"]
            .sum()
            .sort_values("ano_mes")
        )
        fig2 = px.line(serie, x="ano_mes", y="valor_pago", markers=True, title="Total pago por competência")
        fig2.update_layout(height=520)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Seu CSV não tem coluna de data. Se você adicionar uma coluna 'data' ou 'data_lancamento', esse gráfico aparece automaticamente.")

# ----------------------------
# Table + Export
# ----------------------------
st.divider()
st.subheader("📋 Lançamentos (filtrados)")

display_cols = ["numero_lancamento", "fornecedor_funcionario", "valor_pago", "data_lancamento", "ano_mes"]
table = filtered[display_cols].copy()

# Formatação para exibição
table["valor_pago"] = table["valor_pago"].map(brl_format)
table["data_lancamento"] = table["data_lancamento"].dt.strftime("%d/%m/%Y")

st.dataframe(table, use_container_width=True, height=420)

# Download do filtrado
export_df = filtered.copy()
export_name = f"ibem_financeiro_filtrado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
csv_bytes = export_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

st.download_button(
    "⬇️ Baixar CSV filtrado",
    data=csv_bytes,
    file_name=export_name,
    mime="text/csv",
)

if show_raw:
    with st.expander("Ver dados brutos (pós-limpeza)"):
        st.write(filtered.head(50))
