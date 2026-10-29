# -*- coding: utf-8 -*-
import copy
import streamlit as st
import plotly.graph_objects as go
from modelo import sistema, pddd

APP_VERSION = "pddd-ui-2026-10-28-v3"
st.set_page_config(page_title="PDDD | Despacho Hidrotérmico", page_icon="⚡", layout="wide")

# Remove resultados antigos de versões anteriores do app.
if st.session_state.get("app_version") != APP_VERSION:
    for chave in ("resultado", "parametros", "resultado_pddd", "execucao_pddd"):
        st.session_state.pop(chave, None)
    st.session_state["app_version"] = APP_VERSION

st.markdown(r"""
<style>
:root { color-scheme: light !important; }
html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: #ffffff !important;
    color: #0f2747 !important;
}
[data-testid="stHeader"] { background: #ffffff !important; }
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {
    background: #f3f6fa !important;
}
[data-testid="stSidebar"] * { color: #0f2747; }

/* Campos numéricos: fundo branco, texto escuro e botões claros */
[data-testid="stNumberInput"] > div,
[data-testid="stNumberInput"] div[data-baseweb="input"],
[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
[data-testid="stNumberInput"] input {
    background-color: #ffffff !important;
    color: #0f2747 !important;
    -webkit-text-fill-color: #0f2747 !important;
}
[data-testid="stNumberInput"] input {
    border-color: #cbd5e1 !important;
    opacity: 1 !important;
}
[data-testid="stNumberInput"] button {
    background-color: #ffffff !important;
    color: #0f2747 !important;
    border-color: #cbd5e1 !important;
}
[data-testid="stNumberInput"] button svg { fill: #0f2747 !important; }

/* Radio e slider */
[data-testid="stRadio"] label, [data-testid="stSlider"] * { color: #0f2747 !important; }
[data-testid="stSlider"] [role="slider"] { background-color: #2563eb !important; }

/* Botão principal */
.stButton > button[kind="primary"] {
    width: 100%; background: #ff4f55 !important; color: #ffffff !important;
    border: 0 !important; border-radius: 8px !important; font-weight: 700;
}

.block-container { max-width: 1500px; padding-top: 2.0rem; }
.hero { font-size: 2.35rem; font-weight: 800; color: #0f2747; line-height: 1.15; }
.sub { color: #64748b; margin: .55rem 0 1.25rem; }
[data-testid="stMetric"] {
    background: #f8fafc; border: 1px solid #d7e0eb; border-radius: 12px; padding: 1rem;
}
[data-testid="stMetricValue"] { color: #0f2747 !important; font-size: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)


def br(valor, casas=0):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def nome_usina(texto):
    return texto.replace("_", " ").title().replace("Uhe", "UHE").replace("Ute", "UTE")


def formatar_grafico(fig, titulo, eixo_y, eixo_x="Estágio mensal"):
    fig.update_layout(
        title=dict(text=titulo, x=0.01, font=dict(size=20, color="#0f2747")),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(color="#334155", size=13), height=520,
        margin=dict(l=20, r=20, t=65, b=25), hovermode="x unified",
        legend=dict(title="Componente", x=1.01, y=1),
        xaxis=dict(title=eixo_x, gridcolor="#e2e8f0", linecolor="#94a3b8", dtick=1),
        yaxis=dict(title=eixo_y, gridcolor="#e2e8f0", zerolinecolor="#94a3b8"),
    )
    return fig


with st.sidebar:
    st.header("Parâmetros da simulação")
    cenario_nome = st.radio("Cenário hidrológico", ["Otimista", "Pessimista"], index=0)
    cenario = 0 if cenario_nome == "Otimista" else 1

    fator_carga = st.slider(
        "Carga do sistema (%)", min_value=50, max_value=150, value=100, step=5
    )

    st.divider()
    st.subheader("Condição inicial")
    volumes = []
    for uhe in sistema["UHE"]:
        st.caption(
            f'{nome_usina(uhe["Nome"])}: informe um volume inicial entre '
            f'{br(uhe["Vmin"])} e {br(uhe["Vmax"])} hm³.'
        )
        volumes.append(st.number_input(
            f'Volume inicial - {nome_usina(uhe["Nome"])} (hm³)',
            min_value=float(uhe["Vmin"]), max_value=float(uhe["Vmax"]),
            value=float(uhe["VI"]), step=1.0,
        ))

    st.divider()
    st.subheader("Controle de convergência")
    tolerancia = st.number_input(
        "Tolerância máxima", min_value=0.0001, max_value=1_000_000.0,
        value=0.01, step=0.01, format="%.4f",
        help="Diferença máxima admitida entre ZSUP e ZINF.",
    )
    max_iter = st.number_input(
        "Número máximo de iterações", min_value=1, max_value=1000,
        value=100, step=1,
    )
    executar = st.button("Executar PDDD", type="primary", use_container_width=True)

    st.divider()
    st.header("Dados do problema")
    st.subheader("Sistema")
    st.write(f'**Custo do déficit:** R$ {br(sistema["DGer"]["CDef"])} / MWméd')
    st.write(f'**Estágios:** {sistema["DGer"]["Nr_Est"]}')

    with st.expander("Usinas hidrelétricas"):
        for uhe in sistema["UHE"]:
            st.markdown(f'**{nome_usina(uhe["Nome"])}**')
            st.write(f'Produtibilidade: {uhe["Prod"]:.3f} MWméd/hm³')
            st.write(f'Volume mínimo: {br(uhe["Vmin"])} hm³')
            st.write(f'Volume máximo: {br(uhe["Vmax"])} hm³')
            st.write(f'Engolimento: {br(uhe["Engol"], 2)} hm³')

    with st.expander("Usinas termelétricas"):
        for ute in sistema["UTE"]:
            st.markdown(f'**{nome_usina(ute["Nome"])}**')
            st.write(f'Potência máxima: {br(ute["Capac"])} MW')
            st.write(f'CVU: R$ {br(ute["Custo"])} / MWméd')

st.markdown('<div class="hero">⚡ Programação Dinâmica Dual Determinística</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Despacho hidrotérmico, atendimento à demanda e convergência de ZINF e ZSUP.</div>', unsafe_allow_html=True)
st.divider()

# Só executa quando o botão é pressionado. Isso evita exibir resultado antigo.
if executar:
    sis_execucao = copy.deepcopy(sistema)
    sis_execucao["DGer"]["Carga"] = [
        carga * fator_carga / 100.0 for carga in sistema["DGer"]["Carga"]
    ]
    for i, volume in enumerate(volumes):
        sis_execucao["UHE"][i]["VI"] = float(volume)

    try:
        with st.spinner("Executando as passadas forward e backward..."):
            resultado = pddd(
                sis_execucao, cenario=cenario, imprime=False,
                tolerancia=float(tolerancia), max_iter=int(max_iter),
            )
        st.session_state["resultado"] = resultado
        st.session_state["sistema_execucao"] = sis_execucao
        st.session_state["parametros"] = {
            "cenario": cenario_nome,
            "carga_pct": int(fator_carga),
            "volumes": [float(v) for v in volumes],
            "tolerancia": float(tolerancia),
            "max_iter": int(max_iter),
        }
    except Exception as erro:
        st.error(f"Não foi possível executar o modelo: {erro}")
        st.stop()

if "resultado" not in st.session_state:
    st.info("Defina os parâmetros na barra lateral e clique em **Executar PDDD**.")
    st.stop()

r = st.session_state["resultado"]
sis = st.session_state["sistema_execucao"]
p = st.session_state["parametros"]
estagios = list(range(1, sis["DGer"]["Nr_Est"] + 1))

st.header("Resultados do modelo")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Custo total", f'R$ {br(r["DGer"]["CustoTotal"], 2)}')
c2.metric("Iterações", str(r["DGer"]["Nr_Iteracoes"]))
c3.metric("CMO máximo", f'R$ {br(max(r["DGer"]["CMO"]), 2)} / MWméd')
c4.metric("Déficit máximo", f'{br(max(r["DGer"]["Deficit"]), 2)} MWméd')

zinf = r["DGer"]["ZINF"]
zsup = r["DGer"]["ZSUP"]
if not zinf or not zsup:
    st.error("O modelo não retornou o histórico de ZINF e ZSUP.")
    st.stop()
gap = abs(float(zsup[-1]) - float(zinf[-1]))
if gap <= p["tolerancia"]:
    st.success(f'Critério de convergência atendido. Gap final: R$ {br(gap, 4)}.')
else:
    st.warning(f'Gap final: R$ {br(gap, 4)}.')

cores_h = ["#2467c4", "#46a6e8"]
cores_t = ["#ff9800", "#ef4444"]
t1, t2, t3, t4 = st.tabs(["Despacho", "Reservatórios", "Custos marginais", "Convergência"])

with t1:
    fig = go.Figure()
    for i, uhe in enumerate(sis["UHE"]):
        geracao = [uhe["Prod"] * valor for valor in r["UHE"][i]["vt"]]
        fig.add_bar(x=estagios, y=geracao, name=nome_usina(uhe["Nome"]), marker_color=cores_h[i])
    for i, ute in enumerate(sis["UTE"]):
        fig.add_bar(x=estagios, y=r["UTE"][i]["gt"], name=nome_usina(ute["Nome"]), marker_color=cores_t[i])
    fig.add_bar(x=estagios, y=r["DGer"]["Deficit"], name="Déficit", marker_color="#9ca3af")
    fig.add_scatter(x=estagios, y=sis["DGer"]["Carga"], name="Demanda", mode="lines+markers",
                    line=dict(color="#111827", width=3, dash="dash"))
    fig.update_layout(barmode="stack")
    st.plotly_chart(formatar_grafico(fig, "Atendimento à demanda", "Potência média (MWméd)"), use_container_width=True, theme=None)

with t2:
    fig = go.Figure()
    for i, uhe in enumerate(sis["UHE"]):
        fig.add_scatter(x=estagios, y=r["UHE"][i]["vf"], name=nome_usina(uhe["Nome"]),
                        mode="lines+markers", line=dict(color=cores_h[i], width=3))
    st.plotly_chart(formatar_grafico(fig, "Evolução do armazenamento", "Volume final (hm³)"), use_container_width=True, theme=None)

with t3:
    fig = go.Figure()
    fig.add_scatter(x=estagios, y=r["DGer"]["CMO"], name="CMO", mode="lines+markers",
                    line=dict(color="#7c3aed", width=3))
    st.plotly_chart(formatar_grafico(fig, "Custo Marginal de Operação", "CMO (R$/MWméd)"), use_container_width=True, theme=None)

with t4:
    n = min(len(zinf), len(zsup))
    iteracoes = list(range(1, n + 1))
    fig = go.Figure()
    fig.add_scatter(x=iteracoes, y=zinf[:n], name="ZINF", mode="lines+markers", line=dict(color="#2563eb", width=3))
    fig.add_scatter(x=iteracoes, y=zsup[:n], name="ZSUP", mode="lines+markers", line=dict(color="#dc2626", width=3))
    st.plotly_chart(formatar_grafico(fig, "Convergência da PDDD", "Custo (R$)", "Iteração"), use_container_width=True, theme=None)

with st.expander("Resultados numéricos"):
    st.json(r, expanded=False)

st.caption(
    f'Execução exibida: cenário {p["cenario"]} • carga {p["carga_pct"]}% • '
    f'tolerância {p["tolerancia"]} • máximo de {p["max_iter"]} iterações.'
)
