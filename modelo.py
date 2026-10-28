# -*- coding: utf-8 -*-
"""Modelo PDDD determinístico para despacho hidrotermelétrico."""
from copy import deepcopy
import time
import numpy as np
from cvxopt.modeling import variable, op

sistema = {
    "UHE": [
        {"Nome": "UHE CHAVANTES", "Vmax": 8795.0, "Vmin": 5754.0, "VI": 8000.0,
         "Prod": 0.235, "Engol": 1628.0,
         "Afl": [[2156.11,508.90],[1838.59,713.66],[1674.00,656.21],[1153.44,466.56],
                 [1218.67,361.58],[1464.48,155.52],[1098.14,334.80],[883.87,308.02],
                 [1114.56,220.32],[1280.28,334.80],[1101.60,375.84],[1406.16,468.72]]},
        {"Nome": "UHE PIRAJU", "Vmax": 85.0, "Vmin": 83.0, "VI": 84.0,
         "Prod": 0.089, "Engol": 899.16,
         "Afl": [[1379.38,374.98],[1270.08,483.84],[1178.50,455.33],[790.56,336.96],
                 [749.95,267.84],[972.00,90.72],[696.38,227.66],[575.86,214.27],
                 [686.88,168.48],[790.13,241.06],[699.84,266.98],[937.44,308.02]]},
    ],
    "UTE": [
        {"Nome": "UTE Termobahia", "Capac": 186.0, "Custo": 424080.0},
        {"Nome": "UTE Pecém II", "Capac": 144.0, "Custo": 1764000.0},
    ],
    "DGer": {"CDef": 5969520.0,
             "Carga": [530.,508.,516.,437.,420.,401.,390.,411.,454.,490.,506.,504.],
             "Nr_Est": 12, "Nr_Cen": 2},
}


def _valor(x):
    return float(x.value()[0])


def despacho_pddd(sis, vi, afl, cortes, estagio, imprime=False):
    """Resolve um estágio. estagio usa índice Python: 0,...,Nr_Est-1."""
    nuh, nut = len(sis["UHE"]), len(sis["UTE"])
    vf, vt, vv = variable(nuh, "vf"), variable(nuh, "vt"), variable(nuh, "vv")
    gt, deficit, alpha = variable(nut, "gt"), variable(1, "deficit"), variable(1, "alpha")

    fob = sum(u["Custo"] * gt[i] for i, u in enumerate(sis["UTE"]))
    fob += sis["DGer"]["CDef"] * deficit[0]
    fob += sum(0.01 * vv[i] for i in range(nuh)) + alpha[0]

    r = []
    balanco = []
    for i, u in enumerate(sis["UHE"]):
        balanco.append(len(r))
        r.append(vf[i] == float(vi[i]) + float(afl[i]) - vt[i] - vv[i])

    atendimento = sum(u["Prod"] * vt[i] for i, u in enumerate(sis["UHE"]))
    atendimento += sum(gt[i] for i in range(nut)) + deficit[0]
    indice_demanda = len(r)
    r.append(atendimento == sis["DGer"]["Carga"][estagio])

    for i, u in enumerate(sis["UHE"]):
        r += [vf[i] >= u["Vmin"], vf[i] <= u["Vmax"],
              vt[i] >= 0, vt[i] <= u["Engol"], vv[i] >= 0]
    for i, u in enumerate(sis["UTE"]):
        r += [gt[i] >= 0, gt[i] <= u["Capac"]]
    r += [deficit[0] >= 0, alpha[0] >= 0]

    for corte in cortes:
        if corte["Estagio"] == estagio:
            expr = float(corte["Termo_Indep"])
            expr += sum(float(corte["Coefs"][i]) * vf[i] for i in range(nuh))
            r.append(alpha[0] >= expr)

    problema = op(fob, r)
    problema.solve("dense", "glpk")
    if problema.status != "optimal":
        raise RuntimeError(f"O estágio {estagio + 1} não encontrou solução ótima: {problema.status}")

    # No CVXOPT, o multiplicador da igualdade de demanda aparece com sinal oposto ao CMO.
    dger = {"Deficit": _valor(deficit[0]), "CMO": -float(r[indice_demanda].multiplier.value[0]),
            "CustoTotal": float(fob.value()[0]), "CustoFuturo": _valor(alpha[0])}
    uhes = [{"vf": _valor(vf[i]), "vt": _valor(vt[i]), "vv": _valor(vv[i]),
             "cma": float(r[balanco[i]].multiplier.value[0])} for i in range(nuh)]
    utes = [{"gt": _valor(gt[i])} for i in range(nut)]
    if imprime:
        print(f"Estágio {estagio + 1}: custo total = {dger['CustoTotal']:.2f}")
    return {"DGer": dger, "UHE": uhes, "UTE": utes}


def pddd(sis, cenario=0, imprime=False, tolerancia=0.01, max_iter=100):
    """Executa PDDD determinística e devolve séries prontas para o dashboard."""
    if cenario not in range(sis["DGer"]["Nr_Cen"]):
        raise ValueError("Cenário inválido.")
    inicio = time.time()
    nuh, nut, nest = len(sis["UHE"]), len(sis["UTE"]), sis["DGer"]["Nr_Est"]
    cortes, zinf, zsup, memoria_final = [], [], [], []

    for iteracao in range(max_iter):
        memoria, vi = [], [u["VI"] for u in sis["UHE"]]
        custo_imediato = 0.0
        for t in range(nest):
            afl = [u["Afl"][t][cenario] for u in sis["UHE"]]
            res = despacho_pddd(sis, vi, afl, cortes, t, imprime=False)
            memoria.append(res)
            vi = [u["vf"] for u in res["UHE"]]
            custo_imediato += res["DGer"]["CustoTotal"] - res["DGer"]["CustoFuturo"]

        zinf_atual = memoria[0]["DGer"]["CustoTotal"]
        zsup_atual = custo_imediato
        zinf.append(zinf_atual); zsup.append(zsup_atual)
        memoria_final = memoria
        if imprime:
            print(f"Iteração {iteracao + 1}: ZINF={zinf_atual:.2f}, ZSUP={zsup_atual:.2f}")
        if abs(zsup_atual - zinf_atual) <= tolerancia:
            break

        # O custo do estágio t gera um corte para a função de custo futuro do estágio t-1.
        for t in range(nest - 1, 0, -1):
            vi = [memoria[t - 1]["UHE"][i]["vf"] for i in range(nuh)]
            afl = [u["Afl"][t][cenario] for u in sis["UHE"]]
            res = despacho_pddd(sis, vi, afl, cortes, t, imprime=False)
            coefs = [-res["UHE"][i]["cma"] for i in range(nuh)]
            termo = res["DGer"]["CustoTotal"] - sum(vi[i] * coefs[i] for i in range(nuh))
            cortes.append({"Estagio": t - 1, "Termo_Indep": termo, "Coefs": coefs})
    else:
        raise RuntimeError("A PDDD atingiu o número máximo de iterações sem convergir.")

    vf = [[d["UHE"][i]["vf"] for d in memoria_final] for i in range(nuh)]
    vt = [[d["UHE"][i]["vt"] for d in memoria_final] for i in range(nuh)]
    vv = [[d["UHE"][i]["vv"] for d in memoria_final] for i in range(nuh)]
    cma = [[-d["UHE"][i]["cma"] for d in memoria_final] for i in range(nuh)]
    gt = [[d["UTE"][i]["gt"] for d in memoria_final] for i in range(nut)]
    return {
        "DGer": {"CustoTotal": zsup[-1], "CMO": [d["DGer"]["CMO"] for d in memoria_final],
                  "Deficit": [d["DGer"]["Deficit"] for d in memoria_final],
                  "ZINF": zinf, "ZSUP": zsup, "Nr_Iteracoes": len(zinf),
                  "Tempo": time.time() - inicio},
        "UHE": [{"vf": vf[i], "vt": vt[i], "vv": vv[i], "cma": cma[i]} for i in range(nuh)],
        "UTE": [{"gt": gt[i]} for i in range(nut)],
    }
