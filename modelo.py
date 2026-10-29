# -*- coding: utf-8 -*-
"""PDDD determinística robusta e compatível com app.py.

Implementa:
- custos normalizados;
- validação de estados e cortes;
- diagnóstico forward/backward por iteração e estágio;
- teste sem cortes e teste incremental de cortes;
- validação do sinal dos multiplicadores por diferenças finitas;
- associação explícita entre estágio gerador e receptor do corte;
- comparação informativa com valores visíveis no Codigo_5 - otimista.pdf.
"""
from __future__ import annotations

import copy
import math
import time
from typing import Dict, List, Sequence

import numpy as np
from scipy.optimize import linprog

sistema = {
    "UHE": [
        {"Nome":"UHE CHAVANTES","Vmax":8795.0,"Vmin":5754.0,"VI":8000.0,"Prod":0.235,"Engol":1628.0,
         "Afl":[[2156.11,508.90],[1838.59,713.66],[1674.00,656.21],[1153.44,466.56],[1218.67,361.58],[1464.48,155.52],[1098.14,334.80],[883.87,308.02],[1114.56,220.32],[1280.28,334.80],[1101.60,375.84],[1406.16,468.72]]},
        {"Nome":"UHE PIRAJU","Vmax":85.0,"Vmin":83.0,"VI":84.0,"Prod":0.089,"Engol":899.16,
         "Afl":[[1379.38,374.98],[1270.08,483.84],[1178.50,455.33],[790.56,336.96],[749.95,267.84],[972.00,90.72],[696.38,227.66],[575.86,214.27],[686.88,168.48],[790.13,241.06],[699.84,266.98],[937.44,308.02]]},
    ],
    "UTE": [
        {"Nome":"UTE_Termobahia","Capac":186.0,"Custo":424080.0},
        {"Nome":"UTE_Pecém_II","Capac":144.0,"Custo":1764000.0},
    ],
    "DGer":{"CDef":5969520.0,"Carga":[530.,508.,516.,437.,420.,401.,390.,411.,454.,490.,506.,504.],"Nr_Disc":3,"Nr_Est":12,"Nr_Cen":2},
}


def _finito(x, nome):
    a = np.asarray(x, dtype=float)
    if not np.all(np.isfinite(a)):
        raise ValueError(f"{nome} contém NaN ou infinito: {a.tolist()}")
    return a


def _validar_estado(sis, vi, afl, estagio, fase, iteracao):
    vi = _finito(vi, "VI")
    afl = _finito(afl, "AFL")
    if len(vi) != len(sis["UHE"]) or len(afl) != len(sis["UHE"]):
        raise ValueError("VI e AFL devem ter um valor por UHE.")
    if not 0 <= estagio < sis["DGer"]["Nr_Est"]:
        raise ValueError(f"Estágio inválido: {estagio + 1}")
    for i, u in enumerate(sis["UHE"]):
        if vi[i] < u["Vmin"] - 1e-6 or vi[i] > u["Vmax"] + 1e-6:
            raise ValueError(f"{fase}, iteração {iteracao}, estágio {estagio+1}: VI de {u['Nome']} fora dos limites: {vi[i]}")
        if afl[i] < 0:
            raise ValueError(f"Afluência negativa em {u['Nome']}.")
    return vi, afl


def _validar_corte(corte, nuh):
    obrig = {"estagio_receptor", "estagio_gerador", "termo_indep_escalado", "coefs_escalados"}
    if not obrig.issubset(corte):
        raise ValueError(f"Corte incompleto: faltam {sorted(obrig-set(corte))}")
    _finito([corte["termo_indep_escalado"]], "termo independente do corte")
    coefs = _finito(corte["coefs_escalados"], "coeficientes do corte")
    if len(coefs) != nuh:
        raise ValueError("Quantidade de coeficientes do corte incompatível com as UHEs.")
    if corte["estagio_gerador"] != corte["estagio_receptor"] + 1:
        raise ValueError("Associação de corte inválida: o estágio gerador deve ser o sucessor do receptor.")


def despacho_pddd(sis, VI, AFL, cortes, estagio, fase="forward", iteracao=1, imprime=False):
    """Resolve um estágio. `estagio` é zero-based: 0,...,Nr_Est-1."""
    nuh, nut = len(sis["UHE"]), len(sis["UTE"])
    vi, afl = _validar_estado(sis, VI, AFL, estagio, fase, iteracao)
    for c in cortes:
        _validar_corte(c, nuh)

    # x = [vf, vt, vv, gt, deficit, alpha_escalado]
    i_vf = slice(0, nuh); i_vt = slice(nuh, 2*nuh); i_vv = slice(2*nuh, 3*nuh)
    i_gt = slice(3*nuh, 3*nuh+nut); idx_def = 3*nuh+nut; idx_alpha = idx_def+1
    nvar = idx_alpha+1

    escala = float(sis["DGer"]["CDef"])
    if not math.isfinite(escala) or escala <= 0:
        raise ValueError("CDef deve ser positivo e finito para normalização.")
    c = np.zeros(nvar)
    for j,u in enumerate(sis["UTE"]): c[i_gt.start+j] = u["Custo"]/escala
    c[idx_def] = 1.0
    for i in range(nuh): c[i_vv.start+i] = 0.01/escala
    c[idx_alpha] = 1.0

    Aeq, beq = [], []
    # vf + vt + vv = VI + AFL
    for i in range(nuh):
        row=np.zeros(nvar); row[i_vf.start+i]=1; row[i_vt.start+i]=1; row[i_vv.start+i]=1
        Aeq.append(row); beq.append(vi[i]+afl[i])
    # soma(prod*vt)+soma(gt)+deficit = carga
    row=np.zeros(nvar)
    for i,u in enumerate(sis["UHE"]): row[i_vt.start+i]=u["Prod"]
    for j in range(nut): row[i_gt.start+j]=1
    row[idx_def]=1; Aeq.append(row); beq.append(float(sis["DGer"]["Carga"][estagio]))

    Aub, bub = [], []
    ativos = [x for x in cortes if x["estagio_receptor"] == estagio]
    for corte in ativos:
        # alpha >= b + a*vf  => a*vf - alpha <= -b
        row=np.zeros(nvar)
        for i,a in enumerate(corte["coefs_escalados"]): row[i_vf.start+i]=a
        row[idx_alpha]=-1
        Aub.append(row); bub.append(-float(corte["termo_indep_escalado"]))

    bounds=[]
    for u in sis["UHE"]: bounds.append((u["Vmin"],u["Vmax"]))
    for u in sis["UHE"]: bounds.append((0,u["Engol"]))
    bounds += [(0,None)]*nuh
    for u in sis["UTE"]: bounds.append((0,u["Capac"]))
    bounds += [(0,None),(0,None)]

    res=linprog(c,A_ub=np.array(Aub) if Aub else None,b_ub=np.array(bub) if Aub else None,
                A_eq=np.array(Aeq),b_eq=np.array(beq),bounds=bounds,method="highs")
    if not res.success:
        detalhe=(f"fase={fase}, iteração={iteracao}, estágio={estagio+1}, status={res.status}, "
                 f"mensagem={res.message}, VI={vi.tolist()}, AFL={afl.tolist()}, cortes_ativos={len(ativos)}")
        raise RuntimeError("Subproblema não ótimo: "+detalhe)

    x=res.x
    custo_total=float(res.fun*escala); custo_futuro=float(x[idx_alpha]*escala)
    dual_balanco=np.asarray(res.eqlin.marginals[:nuh])*escala
    cmo=float(res.eqlin.marginals[nuh]*escala)
    saida={
        "DGer":{"Déficit":float(x[idx_def]),"Deficit":float(x[idx_def]),"CMO":cmo,
                "CustoTotal":custo_total,"CustoFuturo":custo_futuro},
        "UHE":[{"vf":float(x[i_vf.start+i]),"vt":float(x[i_vt.start+i]),"vv":float(x[i_vv.start+i]),
                "dual_balanco":float(dual_balanco[i]),"cma":float(-dual_balanco[i])} for i in range(nuh)],
        "UTE":[{"gt":float(x[i_gt.start+j])} for j in range(nut)],
        "Diagnostico":{"fase":fase,"iteracao":iteracao,"estagio":estagio+1,"cortes_ativos":len(ativos),
                       "escala_custos":escala,"status_solver":res.message},
    }
    if imprime: print(saida["Diagnostico"], saida["DGer"])
    return saida


def _teste_sem_cortes(sis, cenario):
    vi=[u["VI"] for u in sis["UHE"]]; registros=[]
    for t in range(sis["DGer"]["Nr_Est"]):
        afl=[u["Afl"][t][cenario] for u in sis["UHE"]]
        r=despacho_pddd(sis,vi,afl,[],t,"teste_sem_cortes",0)
        registros.append({"estagio":t+1,"status":"ótimo","custo":r["DGer"]["CustoTotal"]})
        vi=[x["vf"] for x in r["UHE"]]
    return registros


def _validar_sinal_dual(sis, vi, afl, cortes, estagio, base, eps=1e-3):
    testes=[]
    for i,u in enumerate(sis["UHE"]):
        passo=min(eps, u["Vmax"]-vi[i])
        if passo <= 1e-9: continue
        vp=list(vi); vp[i]+=passo
        rp=despacho_pddd(sis,vp,afl,cortes,estagio,"teste_dual",0)
        fd=(rp["DGer"]["CustoTotal"]-base["DGer"]["CustoTotal"])/passo
        dual=base["UHE"][i]["dual_balanco"]
        testes.append({"uhe":u["Nome"],"diferenca_finita":fd,"dual":dual,
                       "erro_abs":abs(fd-dual),"sinal_consistente":(abs(fd)<1e-5 and abs(dual)<1e-2) or fd*dual>=0})
    return testes


def pddd(sis, cenario=0, imprime=False, tolerancia=0.01, max_iter=100):
    if cenario not in range(sis["DGer"]["Nr_Cen"]): raise ValueError("Cenário inválido.")
    if tolerancia <= 0 or max_iter < 1: raise ValueError("Tolerância e máximo de iterações devem ser positivos.")
    sis=copy.deepcopy(sis); inicio=time.time(); nuh=len(sis["UHE"]); nut=len(sis["UTE"]); nest=sis["DGer"]["Nr_Est"]
    diagnosticos={"teste_sem_cortes":_teste_sem_cortes(sis,cenario),"iteracoes":[],"testes_dual":[],"testes_incrementais":[],"cortes":[]}
    cortes=[]; zinf_hist=[]; zsup_hist=[]; memoria=[]; convergiu=False

    for k in range(1,max_iter+1):
        memoria=[]; vi=[u["VI"] for u in sis["UHE"]]; zsup=0.0; log_it={"iteracao":k,"forward":[],"backward":[]}
        for t in range(nest):
            afl=[u["Afl"][t][cenario] for u in sis["UHE"]]
            r=despacho_pddd(sis,vi,afl,cortes,t,"forward",k,imprime)
            memoria.append(r); zsup += r["DGer"]["CustoTotal"]-r["DGer"]["CustoFuturo"]
            log_it["forward"].append(r["Diagnostico"]); vi=[x["vf"] for x in r["UHE"]]
        zinf=memoria[0]["DGer"]["CustoTotal"]; zinf_hist.append(zinf); zsup_hist.append(zsup)
        log_it.update({"ZINF":zinf,"ZSUP":zsup,"gap":abs(zsup-zinf)}); diagnosticos["iteracoes"].append(log_it)
        if abs(zsup-zinf) <= tolerancia: convergiu=True; break

        # O estágio t gera um corte recebido pelo estágio t-1.
        for t in range(nest-1,0,-1):
            vi=[memoria[t-1]["UHE"][i]["vf"] for i in range(nuh)]
            afl=[u["Afl"][t][cenario] for u in sis["UHE"]]
            rb=despacho_pddd(sis,vi,afl,cortes,t,"backward",k)
            log_it["backward"].append(rb["Diagnostico"])
            if k==1: diagnosticos["testes_dual"].extend(_validar_sinal_dual(sis,vi,afl,cortes,t,rb))
            grad=np.array([x["dual_balanco"] for x in rb["UHE"]],dtype=float)
            grad_esc=grad/sis["DGer"]["CDef"]
            q_esc=rb["DGer"]["CustoTotal"]/sis["DGer"]["CDef"]
            termo=float(q_esc-np.dot(grad_esc,np.asarray(vi)))
            corte={"estagio_receptor":t-1,"estagio_gerador":t,"iteracao_geradora":k,
                   "termo_indep_escalado":termo,"coefs_escalados":grad_esc.tolist()}
            _validar_corte(corte,nuh)
            # Teste incremental: o novo corte, isoladamente, deve manter o receptor solucionável.
            existentes=[c for c in cortes if c["estagio_receptor"]==t-1]
            teste=despacho_pddd(sis,vi if t-1==t else [memoria[t-1]["UHE"][i]["vf"] for i in range(nuh)],
                                [u["Afl"][t-1][cenario] for u in sis["UHE"]],existentes+[corte],t-1,
                                "teste_incremental",k)
            diagnosticos["testes_incrementais"].append({"iteracao":k,"receptor":t,"gerador":t+1,"status":"ótimo","cortes_testados":len(existentes)+1})
            cortes.append(corte); diagnosticos["cortes"].append(corte.copy())

    # Comparação informativa com números impressos no PDF, sem forçar igualdade porque o PDF contém índices/transcrições inconsistentes.
    ref={"custo_primeiro_despacho":4.16e8,"vf_chavantes":8.80e3,"vt_chavantes":8.99e2,"vf_piraju":85.0,"vt_piraju":8.99e2,"gt_termobahia":186.0,"gt_pecem":144.0,"deficit":13.9}
    primeiro=memoria[0]
    atual={"custo_primeiro_despacho":primeiro["DGer"]["CustoTotal"],"vf_chavantes":primeiro["UHE"][0]["vf"],"vt_chavantes":primeiro["UHE"][0]["vt"],
           "vf_piraju":primeiro["UHE"][1]["vf"],"vt_piraju":primeiro["UHE"][1]["vt"],"gt_termobahia":primeiro["UTE"][0]["gt"],"gt_pecem":primeiro["UTE"][1]["gt"],"deficit":primeiro["DGer"]["Déficit"]}
    diagnosticos["comparacao_codigo5"]={k:{"referencia_pdf":ref[k],"modelo_corrigido":atual[k],"diferenca":atual[k]-ref[k]} for k in ref}

    vf=[[d["UHE"][i]["vf"] for d in memoria] for i in range(nuh)]; vt=[[d["UHE"][i]["vt"] for d in memoria] for i in range(nuh)]
    vv=[[d["UHE"][i]["vv"] for d in memoria] for i in range(nuh)]; cma=[[d["UHE"][i]["cma"] for d in memoria] for i in range(nuh)]
    gt=[[d["UTE"][i]["gt"] for d in memoria] for i in range(nut)]
    return {"DGer":{"CustoTotal":zsup_hist[-1],"CMO":[d["DGer"]["CMO"] for d in memoria],"Deficit":[d["DGer"]["Déficit"] for d in memoria],
                    "ZINF":zinf_hist,"ZSUP":zsup_hist,"Nr_Iteracoes":len(zinf_hist),"Tempo":time.time()-inicio,"Convergiu":convergiu},
            "UHE":[{"vf":vf[i],"vt":vt[i],"vv":vv[i],"cma":cma[i]} for i in range(nuh)],"UTE":[{"gt":gt[i]} for i in range(nut)],"Diagnosticos":diagnosticos}
