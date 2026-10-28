# -*- coding: utf-8 -*-
import copy
import streamlit as st
import plotly.graph_objects as go
from modelo import sistema, pddd

st.set_page_config(page_title="PDDD | Despacho Hidrotérmico", page_icon="⚡", layout="wide")
st.title("Despacho Hidrotérmico")
st.caption("Planejamento Energético • Programação Dinâmica Dual Determinística (PDDD)")

with st.sidebar:
    st.header("Parâmetros da simulação")
    cenario_nome = st.radio("Cenário hidrológico", ["Otimista", "Pessimista"])
    cenario = 0 if cenario_nome == "Otimista" else 1
    fator_carga = st.slider("Carga do sistema (%)", 50, 150, 100, 5)
    st.subheader("Condições iniciais")
    volumes = []
    for u in sistema["UHE"]:
        volumes.append(st.number_input(f"Volume inicial • {u['Nome'].title()} (hm³)",
                                      min_value=float(u["Vmin"]), max_value=float(u["Vmax"]),
                                      value=float(u["VI"]), step=1.0))
    executar = st.button("Executar PDDD", type="primary", use_container_width=True)
    st.divider()
    st.header("Dados do sistema")
    st.metric("Custo do déficit", f"R$ {sistema['DGer']['CDef']:,.0f}/MWmed".replace(",", "."))
    for u in sistema["UHE"]:
        st.write(f"**{u['Nome'].title()}** · ρ = {u['Prod']:.3f} MWmed/hm³")
    for u in sistema["UTE"]:
        st.write(f"**{u['Nome']}** · {u['Capac']:.0f} MW · CVU R$ {u['Custo']:,.0f}/MWmed".replace(",", "."))

sis = copy.deepcopy(sistema)
sis["DGer"]["Carga"] = [x * fator_carga / 100 for x in sistema["DGer"]["Carga"]]
for i, volume in enumerate(volumes):
    sis["UHE"][i]["VI"] = volume

if executar or "resultado" not in st.session_state:
    try:
        with st.spinner("Executando os passos forward e backward..."):
            st.session_state.resultado = pddd(sis, cenario=cenario)
            st.session_state.parametros = (cenario_nome, fator_carga, tuple(volumes))
    except Exception as erro:
        st.error(f"Não foi possível executar o modelo: {erro}")
        st.stop()

r = st.session_state.resultado
meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
cores_h = ["#1565C0", "#42A5F5"]
cores_t = ["#FF9800", "#E53935"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Custo total", f"R$ {r['DGer']['CustoTotal']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c2.metric("Iterações", r["DGer"]["Nr_Iteracoes"])
c3.metric("CMO máximo", f"R$ {max(r['DGer']['CMO']):,.2f}/MWmed")
c4.metric("Déficit máximo", f"{max(r['DGer']['Deficit']):.2f} MWmed")

def layout(fig, titulo, y):
    fig.update_layout(title=titulo, yaxis_title=y, xaxis_title="Mês", hovermode="x unified",
                      legend_title="Série", margin=dict(l=20, r=20, t=60, b=20))
    return fig

aba1, aba2, aba3, aba4 = st.tabs(["Despacho", "Reservatórios", "Custos marginais", "Convergência"])
with aba1:
    fig = go.Figure()
    for i, u in enumerate(sis["UHE"]):
        gh = [u["Prod"] * x for x in r["UHE"][i]["vt"]]
        fig.add_bar(x=meses, y=gh, name=u["Nome"].title(), marker_color=cores_h[i])
    for i, u in enumerate(sis["UTE"]):
        fig.add_bar(x=meses, y=r["UTE"][i]["gt"], name=u["Nome"], marker_color=cores_t[i])
    fig.add_bar(x=meses, y=r["DGer"]["Deficit"], name="Déficit", marker_color="#9E9E9E")
    fig.add_scatter(x=meses, y=sis["DGer"]["Carga"], name="Carga", mode="lines+markers",
                    line=dict(color="black", width=3, dash="dash"))
    fig.update_layout(barmode="stack")
    st.plotly_chart(layout(fig, "Despacho de geração por estágio", "Geração (MWmed)"), use_container_width=True)
with aba2:
    fig = go.Figure()
    for i, u in enumerate(sis["UHE"]):
        fig.add_scatter(x=meses, y=r["UHE"][i]["vf"], name=u["Nome"].title(), mode="lines+markers",
                        line=dict(color=cores_h[i], width=3))
    st.plotly_chart(layout(fig, "Evolução do armazenamento", "Volume final (hm³)"), use_container_width=True)
with aba3:
    fig = go.Figure()
    fig.add_scatter(x=meses, y=r["DGer"]["CMO"], name="CMO", mode="lines+markers", line=dict(color="#6A1B9A", width=3))
    st.plotly_chart(layout(fig, "Custo Marginal de Operação", "CMO (R$/MWmed)"), use_container_width=True)
    fig2 = go.Figure()
    for i, u in enumerate(sis["UHE"]):
        fig2.add_scatter(x=meses, y=r["UHE"][i]["cma"], name=u["Nome"].title(), mode="lines+markers")
    st.plotly_chart(layout(fig2, "Valor da água", "Valor da água (R$/hm³)"), use_container_width=True)
with aba4:
    it = list(range(1, r["DGer"]["Nr_Iteracoes"] + 1))
    fig = go.Figure()
    fig.add_scatter(x=it, y=r["DGer"]["ZINF"], name="ZINF", mode="lines+markers")
    fig.add_scatter(x=it, y=r["DGer"]["ZSUP"], name="ZSUP", mode="lines+markers")
    st.plotly_chart(layout(fig, "Convergência da PDDD", "Custo (R$)"), use_container_width=True)

st.info(f"Resultado exibido: cenário {st.session_state.parametros[0]}, carga a {st.session_state.parametros[1]}%.")
