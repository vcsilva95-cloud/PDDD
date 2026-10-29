"""Dashboard Streamlit para visualização dos resultados da PDDD."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from modelo import pddd, sistema


st.set_page_config(
    page_title="Dashboard PDDD",
    page_icon="⚡",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp { background-color: #FFFFFF; color: #1F2937; }
        [data-testid="stHeader"] { background-color: rgba(255,255,255,0.95); }
        [data-testid="stSidebar"] { background-color: #F8FAFC; }
        div[data-testid="stMetric"] {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 14px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def executar_modelo(cenario, tolerancia, max_iteracoes):
    return pddd(
        sistema=sistema,
        cenario=cenario,
        imprime=False,
        tolerancia=tolerancia,
        max_iteracoes=max_iteracoes,
    )


def grafico_atendimento(resultado):
    estagios = list(range(1, sistema["DGer"]["Nr_Est"] + 1))
    fig = go.Figure()
    cores_uhe = ["#2563EB", "#06B6D4"]
    cores_ute = ["#F59E0B", "#7C3AED"]

    for i, usina in enumerate(sistema["UHE"]):
        vt = np.asarray(resultado["UHE"][i]["vt"], dtype=float)
        geracao = usina["Prod"] * vt
        fig.add_bar(
            x=estagios,
            y=geracao,
            name=usina["Nome"],
            marker_color=cores_uhe[i % len(cores_uhe)],
            hovertemplate="Estágio %{x}<br>%{y:.2f} MWmed<extra>%{fullData.name}</extra>",
        )

    for i, usina in enumerate(sistema["UTE"]):
        fig.add_bar(
            x=estagios,
            y=resultado["UTE"][i]["gt"],
            name=usina["Nome"],
            marker_color=cores_ute[i % len(cores_ute)],
            hovertemplate="Estágio %{x}<br>%{y:.2f} MWmed<extra>%{fullData.name}</extra>",
        )

    fig.add_bar(
        x=estagios,
        y=resultado["DGer"]["Deficit"],
        name="Déficit",
        marker_color="#DC2626",
        hovertemplate="Estágio %{x}<br>%{y:.2f} MWmed<extra>Déficit</extra>",
    )
    fig.add_scatter(
        x=estagios,
        y=sistema["DGer"]["Carga"],
        name="Demanda",
        mode="lines+markers",
        line=dict(color="#111827", width=3, dash="dash"),
        hovertemplate="Estágio %{x}<br>%{y:.2f} MWmed<extra>Demanda</extra>",
    )
    fig.update_layout(
        title="Atendimento à demanda",
        barmode="stack",
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="Estágio mensal",
        yaxis_title="Potência média (MWmed)",
        hovermode="x unified",
        legend_title="Componente",
        margin=dict(l=30, r=20, t=65, b=30),
    )
    fig.update_xaxes(dtick=1, gridcolor="#E5E7EB")
    fig.update_yaxes(rangemode="tozero", gridcolor="#E5E7EB")
    return fig


def grafico_convergencia(resultado):
    zinf = np.asarray(resultado["DGer"]["ZINF"], dtype=float)
    zsup = np.asarray(resultado["DGer"]["ZSUP"], dtype=float)
    mascara = np.isfinite(zinf) & np.isfinite(zsup)
    zinf, zsup = zinf[mascara], zsup[mascara]
    iteracoes = np.arange(1, len(zinf) + 1)

    fig = go.Figure()
    fig.add_scatter(
        x=iteracoes, y=zinf, name="ZINF", mode="lines+markers",
        line=dict(color="#2563EB", width=3),
        hovertemplate="Iteração %{x}<br>R$ %{y:,.2f}<extra>ZINF</extra>",
    )
    fig.add_scatter(
        x=iteracoes, y=zsup, name="ZSUP", mode="lines+markers",
        line=dict(color="#DC2626", width=3),
        hovertemplate="Iteração %{x}<br>R$ %{y:,.2f}<extra>ZSUP</extra>",
    )
    fig.update_layout(
        title="Convergência da PDDD",
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="Iteração",
        yaxis_title="Custo (R$)",
        hovermode="x unified",
        legend_title="Limite",
        margin=dict(l=30, r=20, t=65, b=30),
    )
    fig.update_xaxes(dtick=1, gridcolor="#E5E7EB")
    fig.update_yaxes(gridcolor="#E5E7EB", tickformat=",.2f")
    return fig


st.title("⚡ Programação Dinâmica Dual Determinística")
st.caption("Despacho hidrotérmico, atendimento à demanda e convergência de ZINF e ZSUP.")

with st.sidebar:
    st.header("Configurações")
    cenario = st.selectbox(
        "Cenário de afluência",
        options=[0, 1],
        format_func=lambda x: "Cenário 1" if x == 0 else "Cenário 2",
    )
    tolerancia = st.number_input(
        "Tolerância absoluta (R$)", min_value=0.01, value=0.01, step=0.01,
        format="%.2f",
    )
    max_iteracoes = st.number_input(
        "Máximo de iterações", min_value=1, max_value=500, value=100, step=1,
    )
    executar = st.button("Executar PDDD", type="primary", use_container_width=True)

if executar or "resultado_pddd" not in st.session_state:
    try:
        with st.spinner("Resolvendo a PDDD..."):
            st.session_state.resultado_pddd = executar_modelo(
                cenario, float(tolerancia), int(max_iteracoes)
            )
    except Exception as erro:
        st.error(f"Não foi possível executar o modelo: {erro}")
        st.stop()

resultado = st.session_state.resultado_pddd
zinf_final = float(resultado["DGer"]["ZINF"][-1])
zsup_final = float(resultado["DGer"]["ZSUP"][-1])
gap_final = abs(zsup_final - zinf_final)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Custo da política", f"R$ {resultado['DGer']['CustoTotal']:,.2f}")
c2.metric("Iterações", resultado["DGer"]["Nr_Iteracoes"])
c3.metric("ZINF final", f"R$ {zinf_final:,.2f}")
c4.metric("Gap final", f"R$ {gap_final:,.2f}")

if resultado["DGer"]["Convergiu"]:
    st.success("O critério de convergência foi atendido.")
else:
    st.warning("O limite máximo de iterações foi atingido antes da tolerância.")

st.plotly_chart(grafico_atendimento(resultado), use_container_width=True)
st.plotly_chart(grafico_convergencia(resultado), use_container_width=True)

with st.expander("Resultados numéricos"):
    st.json(resultado)

