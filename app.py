# -*- coding: utf-8 -*-
import copy
import streamlit as st
import plotly.graph_objects as go
from modelo import sistema, pddd

st.set_page_config(page_title="PDDD | Despacho Hidrotérmico", page_icon="⚡", layout="wide")
st.markdown("""
<style>
.stApp{background:#fff;color:#12213a}.block-container{max-width:1480px;padding-top:2.2rem}
[data-testid="stHeader"]{background:#fff}[data-testid="stSidebar"]{background:#f3f6fa;border-right:1px solid #d7dee8}
[data-testid="stSidebar"] *{color:#12213a!important}h1,h2,h3,h4,p,label{color:#12213a!important}
.hero{font-size:2.45rem;font-weight:800;line-height:1.12;color:#12213a}.sub{color:#64748b;margin:.6rem 0 1.4rem}
.side-value{font-size:1.55rem;line-height:1.2;margin:.2rem 0 1rem}.side-card{line-height:1.7;margin-bottom:1rem}
[data-testid="stMetric"]{background:#f8fafc;border:1px solid #d8e0ea;padding:1rem;border-radius:12px;min-height:112px}
[data-testid="stMetricValue"]{color:#12213a!important;font-size:1.45rem!important}.stButton>button{width:100%;background:#ff4f55;color:#fff!important;border:0;font-weight:700}
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div{background:#10151d!important;border-color:#10151d!important}
div[data-baseweb="select"] *,div[data-baseweb="input"] input{color:#fff!important}[data-testid="stTabs"] button p{color:#12213a!important;font-weight:650}
</style>""", unsafe_allow_html=True)

def br(v, c=0):
    return f"{v:,.{c}f}".replace(",","X").replace(".",",").replace("X",".")

def nome(v):
    return v.replace("_"," ").title().replace("Uhe","UHE").replace("Ute","UTE")

def grafico(fig, titulo, y, x="Estágio mensal"):
    fig.update_layout(title=dict(text=titulo,font=dict(size=20,color="#12213a"),x=.01),paper_bgcolor="#fff",plot_bgcolor="#fff",font=dict(color="#334155",size=13),height=520,margin=dict(l=20,r=20,t=65,b=25),hovermode="x unified",legend=dict(title="Componente",x=1.01,y=1),xaxis=dict(title=x,gridcolor="#e2e8f0",linecolor="#94a3b8",dtick=1),yaxis=dict(title=y,gridcolor="#e2e8f0",zerolinecolor="#94a3b8"))
    return fig

with st.sidebar:
    st.header("Dados do problema")
    st.subheader("Sistema")
    st.caption("Custo do déficit")
    st.markdown(f'<div class="side-value">R$ {br(sistema["DGer"]["CDef"])} / MWméd</div>',unsafe_allow_html=True)
    st.caption(f'{sistema["DGer"]["Nr_Est"]} estágios mensais • {sistema["DGer"]["Nr_Cen"]} trajetórias')
    st.subheader("Usinas Hidrelétricas")
    for u in sistema["UHE"]:
        txt=(f'<div class="side-card"><b>{nome(u["Nome"])}</b><br>'
             f'Produtibilidade (ρ): {u["Prod"]:.3f} MWméd/hm³<br>'
             f'Volume inicial: {br(u["VI"])} hm³<br>Volume máximo: {br(u["Vmax"])} hm³<br>'
             f'Volume mínimo: {br(u["Vmin"])} hm³<br>Volume útil: {br(u["Vmax"]-u["Vmin"])} hm³<br>'
             f'Engolimento: {br(u["Engol"],2)} hm³</div>')
        st.markdown(txt,unsafe_allow_html=True)
    st.subheader("Usinas Termelétricas")
    for u in sistema["UTE"]:
        st.markdown(f'<div class="side-card"><b>{nome(u["Nome"])}</b><br>Potência máxima: {br(u["Capac"])} MW<br>CVU: R$ {br(u["Custo"])} / MWméd</div>',unsafe_allow_html=True)
    st.divider(); st.subheader("Parâmetros da PDDD")
    cen_nome=st.selectbox("Trajetória hidrológica",["Cenário 1 • Otimista","Cenário 2 • Pessimista"])
    cen=0 if cen_nome.startswith("Cenário 1") else 1
    tol=st.number_input("Tolerância absoluta",min_value=.0001,max_value=1000000.,value=.01,step=.01,format="%.4f")
    maxit=st.number_input("Máximo de iterações",min_value=1,max_value=1000,value=100,step=1)
    rodar=st.button("Executar PDDD",type="primary")

st.markdown('<div class="hero">⚡ Programação Dinâmica Dual Determinística</div>',unsafe_allow_html=True)
st.markdown('<div class="sub">Despacho hidrotérmico, atendimento à demanda e convergência de ZINF e ZSUP.</div>',unsafe_allow_html=True)
st.divider(); sis=copy.deepcopy(sistema)
if rodar or "resultado" not in st.session_state:
    try:
        with st.spinner("Executando as passadas forward e backward..."):
            st.session_state.resultado=pddd(sis,cenario=cen,imprime=False,tolerancia=float(tol),max_iter=int(maxit))
            st.session_state.parametros=(cen_nome,float(tol),int(maxit))
    except Exception as e:
        st.error(f"Não foi possível executar o modelo: {e}"); st.stop()
r=st.session_state.resultado; p=st.session_state.parametros; est=list(range(1,sis["DGer"]["Nr_Est"]+1))
st.header("Resultados do modelo")
a,b,c,d=st.columns(4)
a.metric("Custo total",f'R$ {br(r["DGer"]["CustoTotal"],2)}'); b.metric("Iterações",r["DGer"]["Nr_Iteracoes"])
c.metric("CMO máximo",f'R$ {br(max(r["DGer"]["CMO"]),2)} / MWméd'); d.metric("Déficit máximo",f'{br(max(r["DGer"]["Deficit"]),2)} MWméd')
gap=abs(r["DGer"]["ZSUP"][-1]-r["DGer"]["ZINF"][-1])
(st.success if gap<=p[1] else st.warning)(f'Gap final: R$ {br(gap,4)}.')
cores_h=["#2467c4","#42a5f5"]; cores_t=["#ff9800","#ef4444"]
t1,t2,t3,t4=st.tabs(["Despacho","Reservatórios","Custos marginais","Convergência"])
with t1:
    f=go.Figure()
    for i,u in enumerate(sis["UHE"]): f.add_bar(x=est,y=[u["Prod"]*v for v in r["UHE"][i]["vt"]],name=nome(u["Nome"]),marker_color=cores_h[i])
    for i,u in enumerate(sis["UTE"]): f.add_bar(x=est,y=r["UTE"][i]["gt"],name=nome(u["Nome"]),marker_color=cores_t[i])
    f.add_bar(x=est,y=r["DGer"]["Deficit"],name="Déficit",marker_color="#9ca3af")
    f.add_scatter(x=est,y=sis["DGer"]["Carga"],name="Demanda",mode="lines+markers",line=dict(color="#111827",width=3,dash="dash")); f.update_layout(barmode="stack")
    st.plotly_chart(grafico(f,"Atendimento à demanda","Potência média (MWméd)"),use_container_width=True,theme=None)
with t2:
    f=go.Figure()
    for i,u in enumerate(sis["UHE"]): f.add_scatter(x=est,y=r["UHE"][i]["vf"],name=nome(u["Nome"]),mode="lines+markers",line=dict(color=cores_h[i],width=3))
    st.plotly_chart(grafico(f,"Evolução do armazenamento","Volume final (hm³)"),use_container_width=True,theme=None)
with t3:
    f=go.Figure(); f.add_scatter(x=est,y=r["DGer"]["CMO"],name="CMO",mode="lines+markers",line=dict(color="#7c3aed",width=3))
    st.plotly_chart(grafico(f,"Custo Marginal de Operação","CMO (R$/MWméd)"),use_container_width=True,theme=None)
    f=go.Figure()
    for i,u in enumerate(sis["UHE"]): f.add_scatter(x=est,y=r["UHE"][i]["cma"],name=nome(u["Nome"]),mode="lines+markers",line=dict(color=cores_h[i],width=3))
    st.plotly_chart(grafico(f,"Valor da água","CMA (R$/hm³)"),use_container_width=True,theme=None)
with t4:
    it=list(range(1,r["DGer"]["Nr_Iteracoes"]+1)); f=go.Figure()
    f.add_scatter(x=it,y=r["DGer"]["ZINF"],name="ZINF",mode="lines+markers",line=dict(color="#2563eb",width=3)); f.add_scatter(x=it,y=r["DGer"]["ZSUP"],name="ZSUP",mode="lines+markers",line=dict(color="#dc2626",width=3))
    st.plotly_chart(grafico(f,"Convergência da PDDD","Custo (R$)","Iteração"),use_container_width=True,theme=None)
with st.expander("Resultados numéricos"): st.json(r,expanded=False)
st.caption(f"Execução exibida: {p[0]} • tolerância {p[1]} • máximo de {p[2]} iterações.")
