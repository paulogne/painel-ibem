import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página - Visual Institucional IBEM
st.set_page_config(page_title="Dashboard Financeiro IBEM", layout="wide", page_icon="🏛️")

# --- ESTILIZAÇÃO CSS (Visual Limpo e Profissional) ---
st.markdown("""
<style>
    .big-font { font-size: 24px !important; font-weight: bold; color: #2c3e50; }
    .kpi-card {
        background-color: #ffffff;
        border-left: 5px solid #3498db;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    h1 { color: #2c3e50; }
    h3 { color: #34495e; }
</style>
""", unsafe_allow_html=True)

# --- INTELIGÊNCIA DE CLASSIFICAÇÃO IBEM ---
def classificar_ibem(row):
    # Converte para minúsculas para facilitar a busca
    hist = str(row['Histórico']).lower()
    
    # 1. Manutenção e Estrutura (Prioridade Alta - Resolve compras em nome de PF)
    termos_obra = ['cimento', 'tinta', 'fita isolante', 'adaptador', 'bejamin', 'lâmpada', 'cano', 'obra', 'reparo', 'lixeiras', 'tijolo', 'tomada', 'bucha', 'parafuso']
    if any(t in hist for t in termos_obra):
        return 'Manutenção e Obras'
    
    # 2. Secretaria e Administrativo
    termos_escritorio = ['resma', 'papel', 'caneta', 'impressão', 'tinta', 'caderno', 'fotográfico', 'envelope', 'crachá', 'copo']
    if any(t in hist for t in termos_escritorio):
        return 'Material de Escritório/Consumo'
    
    # 3. Limpeza
    termos_limpeza = ['papel higiênico', 'limpeza', 'vassoura', 'sabão', 'água', 'sanitária', 'detergente']
    if any(t in hist for t in termos_limpeza):
        return 'Limpeza e Higiene'
        
    # 4. Marketing e Divulgação
    termos_mkt = ['panfletagem', 'divulgação', 'design', 'banner', 'panfleto', 'midia', 'facebook', 'instagram', 'trafego']
    if any(t in hist for t in termos_mkt):
        return 'Marketing'
    
    # 5. Financeiro/Bancário
    termos_fin = ['pix', 'transferência', 'tarifas', 'banco', 'resgate', 'pagamento conta']
    if any(t in hist for t in termos_fin):
        return 'Transações Financeiras'

    # 6. Reembolsos de Alunos
    termos_reembolso = ['dev. matricula', 'devolução', 'estorno']
    if any(t in hist for t in termos_reembolso):
        return 'Reembolsos/Cancelamentos'
    
    return 'Outros/Não Identificado'

# --- CARREGAR DADOS ---
@st.cache_data
def carregar_dados(arquivo):
    try:
        df = pd.read_csv(arquivo, sep=';', encoding='utf-8')
    except:
        df = pd.read_csv(arquivo, sep=';', encoding='latin1')
    
    # Ajustar nomes de colunas se necessário (removendo acentos bugados)
    df.columns = ['Nº Lanç.', 'Fornecedor', 'Banco', 'Histórico', 'Venc.', 'Data Pgto.', 'Valor Pago']

    # Limpeza de Valor (R$)
    def limpar_moeda(x):
        if isinstance(x, str):
            if ',' in x:
                x = x.replace('.', '').replace(',', '.')
        return float(x)
    
    df['Valor Pago'] = df['Valor Pago'].apply(limpar_moeda)
    df['Data Pgto.'] = pd.to_datetime(df['Data Pgto.'], dayfirst=True, errors='coerce')
    
    # Aplica a inteligência
    df['Categoria IBEM'] = df.apply(classificar_ibem, axis=1)
    
    return df

# --- INTERFACE ---
st.title("🏛️ Painel de Custos - IBEM")
st.markdown("Visão consolidada das despesas com classificação inteligente de histórico.")

uploaded_file = st.file_uploader("📂 Arraste seu CSV aqui", type=['csv'])

if uploaded_file:
    df = carregar_dados(uploaded_file)
    
    # --- FILTROS LATERAIS ---
    st.sidebar.header("Filtros")
    cats = df['Categoria IBEM'].unique()
    sel_cats = st.sidebar.multiselect("Filtrar Categoria", cats, default=cats)
    
    df_filtered = df[df['Categoria IBEM'].isin(sel_cats)]
    
    # --- KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    total = df_filtered['Valor Pago'].sum()
    media = df_filtered['Valor Pago'].mean()
    
    col1.metric("Total Gasto", f"R$ {total:,.2f}")
    col2.metric("Média por Compra", f"R$ {media:,.2f}")
    col3.metric("Nº Lançamentos", len(df_filtered))
    
    # --- GRÁFICOS ---
    c1, c2 = st.columns(2)
    
    # Gráfico de Rosca (Categorias)
    fig_pie = px.pie(df_filtered, values='Valor Pago', names='Categoria IBEM', 
                     title='Distribuição de Gastos (Classificação Automática)',
                     hole=0.4)
    c1.plotly_chart(fig_pie, use_container_width=True)
    
    # Gráfico de Barras (Quem gastou - Top Fornecedores)
    gastos_fornecedor = df_filtered.groupby('Fornecedor')['Valor Pago'].sum().sort_values(ascending=False).head(10)
    fig_bar = px.bar(gastos_fornecedor, orientation='h', 
                     title="Top 10 Destinos do Dinheiro (Fornecedores/Pessoas)",
                     text_auto=True)
    c2.plotly_chart(fig_bar, use_container_width=True)
    
    # --- AUDITORIA ---
    st.markdown("### 📝 Detalhamento para Auditoria")
    st.markdown("Verifique abaixo como o sistema reclassificou os gastos de 'Paulo Henrique' e outros.")
    st.dataframe(df_filtered[['Data Pgto.', 'Fornecedor', 'Histórico', 'Valor Pago', 'Categoria IBEM']], use_container_width=True)

else:
    st.info("Por favor, faça upload do arquivo CSV para iniciar a análise.")