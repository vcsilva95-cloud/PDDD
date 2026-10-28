# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
import copy

from modelo import sistema, pl_unico

# --------------------------------------------------
# CONFIGURAÃ‡ÃƒO DA PÃGINA
# --------------------------------------------------

st.set_page_config(
    page_title="Despacho Hidrotérmico",
    page_icon="âš¡",
    layout="wide"
)

st.title("Despacho Hidrotérmico")
st.write("Planejamento Energético - PL Único")


# --------------------------------------------------
# DADOS DO PROBLEMA - BARRA LATERAL
# --------------------------------------------------
st.sidebar.header("Dados do problema")

st.sidebar.subheader("Sistema")
st.sidebar.metric(
    label="Custo do déficit",
    value=f"R$ {sistema['DGer']['CDef']:,.0f} / MWméd".replace(",", ".")
)

st.sidebar.subheader("Usinas Hidrelétricas")
for uhe in sistema["UHE"]:
    st.sidebar.markdown(f"**{uhe['Nome'].replace('UHE ', 'UHE ').title()}**")
    st.sidebar.write(f"Produtibilidade (ρ): {uhe['Prod']:.3f} MWmed/hm³")
    st.sidebar.write(f"Volume máximo: {uhe['Vmax']:,.0f} hm³".replace(",", "."))
    st.sidebar.write(f"Volume mínimo: {uhe['Vmin']:,.0f} hm³".replace(",", "."))
    st.sidebar.write(f"Volume Útil: {uhe['Vmax'] - uhe['Vmin']:,.0f} hm³".replace(",", "."))

st.sidebar.subheader("Usinas Termelétricas")
for ute in sistema["UTE"]:
    st.sidebar.markdown(f"**{ute['Nome'].replace('_', ' ')}**")
    st.sidebar.write(f"Potência máxima: {ute['Capac']:.0f} MW")
    st.sidebar.write(f"CVU: R$ {ute['Custo']:,.0f} / MWméd".replace(",", "."))

st.sidebar.divider()

# --------------------------------------------------
# PARAMETROS DA SIMULAÃ‡ÃƒO (CARGA E CENARIO)
# --------------------------------------------------

st.sidebar.header("Parâmetros da simulação")

cenario_nome = st.sidebar.radio(
    "Cenário hidrológico",
    options=["Otimista", "Pessimista"],
    index=0
)

if cenario_nome == "Otimista":
    cenario = 0
else:
    cenario = 1


fator_carga = st.sidebar.slider(
    "Carga do sistema (%)",
    min_value=50,
    max_value=150,
    value=100,
    step=5
)

# --------------------------------------------------
# ALTERAÃ‡ÃƒO DA CARGA PELO SLIDER
# --------------------------------------------------

# Faz uma cÃ³pia do sistema original
sistema_simulacao = copy.deepcopy(sistema)

# Calcula a carga correspondente ao percentual escolhido
carga_modificada = [
    carga * fator_carga / 100
    for carga in sistema["DGer"]["Carga"]
]

# Coloca a carga modificada no sistema que serÃ¡ otimizado
sistema_simulacao["DGer"]["Carga"] = carga_modificada

st.sidebar.divider()

st.sidebar.subheader("Condição inicial")

st.sidebar.caption(
    "UHE Chavantes: informe um volume inicial entre "
    "5.754 e 8.795 hm³."
)

vi_chavantes = st.sidebar.number_input(
    "Volume inicial - UHE Chavantes (hm³)",
    min_value=5754.0,
    max_value=8795.0,
    value=7500.0,
    step=1.0,
    format="%.0f"
)


# Altera a carga pelo percentual escolhido
carga_modificada = [
    carga * fator_carga / 100
    for carga in sistema["DGer"]["Carga"]
]

sistema_simulacao["DGer"]["Carga"] = carga_modificada

# Altera o volume inicial de Chavantes
sistema_simulacao["UHE"][0]["VI"] = vi_chavantes

# --------------------------------------------------
# EXECUÃ‡ÃƒO DO MODELO
# --------------------------------------------------

resultado = pl_unico(sistema_simulacao,cenario,False)


# --------------------------------------------------
# RESULTADOS
# --------------------------------------------------
st.divider()
st.header("Resultados do Modelo")

estagios = list(range(1, 13))
gh_chavantes = resultado["UHE"][0]["gh"]
gh_piraju = resultado["UHE"][1]["gh"]
gt_termobahia = resultado["UTE"][0]["gt"]
gt_pecem = resultado["UTE"][1]["gt"]
deficit = resultado["Deficit"]
carga_modelo = sistema_simulacao["DGer"]["Carga"]

# 1) DESPACHO DE GERAÃ‡ÃƒO
st.subheader("Despacho de Geração por Estágio")
fig_despacho = go.Figure()
for y, nome, cor in [
    (gh_chavantes, "UHE Chavantes", "#1565C0"),
    (gh_piraju, "UHE Piraju", "#42A5F5"),
    (gt_termobahia, "UTE Termobahia", "#FF9800"),
    (gt_pecem, "UTE Pecem II", "#E53935"),
    (deficit, "Déficit", "#9E9E9E"),
]:
    fig_despacho.add_trace(go.Bar(x=estagios, y=y, name=nome, marker_color=cor))
fig_despacho.add_trace(go.Scatter(
    x=estagios, y=carga_modelo, mode="lines+markers", name="Carga",
    line=dict(color="black", width=3, dash="dash"),
    marker=dict(size=7, color="black")
))
fig_despacho.update_layout(
    title="Despacho de Geração por Estágio", xaxis_title="Estágio",
    yaxis_title="Geração (MWmed)", barmode="stack",
    legend_title="Fonte de geração", hovermode="x unified"
)
fig_despacho.update_xaxes(tickmode="linear", dtick=1)
st.plotly_chart(fig_despacho, use_container_width=True)

# 2) ARMAZENAMENTO
st.divider()
st.subheader("Evolução do Armazenamento")
vf_chavantes = resultado["UHE"][0]["vf"]
vf_piraju = resultado["UHE"][1]["vf"]
fig_armazenamento = go.Figure()
fig_armazenamento.add_trace(go.Scatter(
    x=estagios, y=vf_chavantes, mode="lines+markers", name="UHE Chavantes",
    line=dict(color="#1565C0", width=3), marker=dict(size=7)
))
fig_armazenamento.add_trace(go.Scatter(
    x=estagios, y=vf_piraju, mode="lines+markers", name="UHE Piraju",
    line=dict(color="#42A5F5", width=3), marker=dict(size=7)
))
fig_armazenamento.update_layout(
    title="Volume Armazenado Final por Estágio", xaxis_title="Estágio",
    yaxis_title="Volume armazenado (hmÂ³)", hovermode="x unified",
    legend_title="Reservatório"
)
fig_armazenamento.update_xaxes(tickmode="linear", dtick=1)
st.plotly_chart(fig_armazenamento, use_container_width=True)

# 3) CUSTO DE OPERAÃ‡ÃƒO
st.divider()
st.subheader("Custo de Operação por Estágio")
cvu_termobahia = sistema["UTE"][0]["Custo"]
cvu_pecem = sistema["UTE"][1]["Custo"]
custo_deficit = sistema["DGer"]["CDef"]
custo_termobahia = [gt_termobahia[i] * cvu_termobahia for i in range(12)]
custo_pecem = [gt_pecem[i] * cvu_pecem for i in range(12)]
custo_deficit_estagio = [deficit[i] * custo_deficit for i in range(12)]
custo_estagio = [
    custo_termobahia[i] + custo_pecem[i] + custo_deficit_estagio[i]
    for i in range(12)
]
custo_total_operacao = sum(custo_estagio)
fig_custo = go.Figure()
fig_custo.add_trace(go.Bar(x=estagios, y=custo_termobahia, name="UTE Termobahia", marker_color="#FF9800"))
fig_custo.add_trace(go.Bar(x=estagios, y=custo_pecem, name="UTE Pecém II", marker_color="#E53935"))
fig_custo.add_trace(go.Bar(x=estagios, y=custo_deficit_estagio, name="Déficit", marker_color="#9E9E9E"))
fig_custo.update_layout(
    xaxis_title="Estágio", yaxis_title="Custo (R$)", barmode="stack",
    legend_title="Componente do custo", hovermode="x unified"
)
fig_custo.update_xaxes(tickmode="linear", dtick=1)
st.plotly_chart(fig_custo, use_container_width=True)

custo_formatado = (f"{custo_total_operacao:,.2f}"
                   .replace(",", "X").replace(".", ",").replace("X", "."))
st.metric(label="Custo total de operação", value=f"R$ {custo_formatado}")

# RESUMO DA SIMULAÃ‡ÃƒO
st.divider()
st.subheader("Cenário de carga")
st.write(f"A carga utilizada na otimização será {fator_carga}% da carga original.")
if fator_carga == 100:
    st.success("Carga original do sistema")
elif fator_carga > 100:
    st.warning(f"Carga aumentada em {fator_carga - 100}%")
else:
    st.info(f"Carga reduzida em {100 - fator_carga}%")
st.info(f"Cenário hidrológico selecionado: **{cenario_nome}**")
