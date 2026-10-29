"""Modelo de Programação Dinâmica Dual Determinística (PDDD).

Baseado no exercício fornecido pela usuária, com correções no balanço hídrico,
no índice da carga, na consolidação do déficit e na passagem backward.
"""

import time
import numpy as np
from cvxopt.modeling import variable, op


# -----------------------------------------------------------------------------
# Dados do sistema
# -----------------------------------------------------------------------------
lista_uhe = [
    {
        "Nome": "UHE CHAVANTES",
        "Vmax": 8795.0,
        "Vmin": 5754.0,
        "VI": 8000.0,
        "Prod": 0.235,
        "Engol": 1628.0,
        "Afl": [
            [2156.11, 508.90], [1838.59, 713.66], [1674.00, 656.21],
            [1153.44, 466.56], [1218.67, 361.58], [1464.48, 155.52],
            [1098.14, 334.80], [883.87, 308.02], [1114.56, 220.32],
            [1280.28, 334.80], [1101.60, 375.84], [1406.16, 468.72],
        ],
    },
    {
        "Nome": "UHE PIRAJU",
        "Vmax": 85.0,
        "Vmin": 83.0,
        "VI": 84.0,
        "Prod": 0.089,
        "Engol": 899.16,
        "Afl": [
            [1379.38, 374.98], [1270.08, 483.84], [1178.50, 455.33],
            [790.56, 336.96], [749.95, 267.84], [972.00, 90.72],
            [696.38, 227.66], [575.86, 214.27], [686.88, 168.48],
            [790.13, 241.06], [699.84, 266.98], [937.44, 308.02],
        ],
    },
]

lista_ute = [
    {"Nome": "UTE Termobahia", "Capac": 186.0, "Custo": 424080.0},
    {"Nome": "UTE Pecém II", "Capac": 144.0, "Custo": 1764000.0},
]

d_gerais = {
    "CDef": 5969520.0,
    "Carga": [530.0, 508.0, 516.0, 437.0, 420.0, 401.0,
              390.0, 411.0, 454.0, 490.0, 506.0, 504.0],
    "Nr_Disc": 3,
    "Nr_Est": 12,
    "Nr_Cen": 2,
}

sistema = {"DGer": d_gerais, "UHE": lista_uhe, "UTE": lista_ute}


def _valor(escalar):
    """Converte o escalar do CVXOPT em float."""
    return float(escalar.value()[0])


def despacho_pddd(sistema, vi, afl, pote_de_corte, iest, imprime=False):
    """Resolve o despacho hidrotérmico de um estágio.

    Parameters
    ----------
    iest : int
        Estágio no padrão 1..Nr_Est.
    """
    num_uhe = len(sistema["UHE"])
    num_ute = len(sistema["UTE"])

    vf = variable(num_uhe, "Volume final")
    vt = variable(num_uhe, "Volume turbinado")
    vv = variable(num_uhe, "Volume vertido")
    gt = variable(num_ute, "Geração térmica")
    deficit = variable(1, "Déficit")
    alpha = variable(1, "Custo futuro")

    fob = 0
    for i, usina in enumerate(sistema["UTE"]):
        fob += usina["Custo"] * gt[i]
    fob += sistema["DGer"]["CDef"] * deficit[0]
    for i in range(num_uhe):
        fob += 0.01 * vv[i]
    fob += alpha[0]

    restricoes = []

    # Balanço hídrico individualizado por UHE.
    for i in range(num_uhe):
        restricoes.append(
            vf[i] == float(vi[i]) + float(afl[i]) - vt[i] - vv[i]
        )

    # Atendimento à demanda. iest é 1-based; a lista Carga é 0-based.
    atendimento = 0
    for i, usina in enumerate(sistema["UHE"]):
        atendimento += usina["Prod"] * vt[i]
    for i in range(num_ute):
        atendimento += gt[i]
    atendimento += deficit[0]
    restricao_demanda = len(restricoes)
    restricoes.append(atendimento == sistema["DGer"]["Carga"][iest - 1])

    for i, usina in enumerate(sistema["UHE"]):
        restricoes.extend([
            vf[i] >= usina["Vmin"],
            vf[i] <= usina["Vmax"],
            vt[i] >= 0,
            vt[i] <= usina["Engol"],
            vv[i] >= 0,
        ])

    for i, usina in enumerate(sistema["UTE"]):
        restricoes.extend([gt[i] >= 0, gt[i] <= usina["Capac"]])

    restricoes.extend([deficit[0] >= 0, alpha[0] >= 0])

    for corte in pote_de_corte:
        # O corte produzido no estágio t aproxima o custo a partir de t+1.
        if corte["Estagio"] == iest:
            equacao = float(corte["Termo_Indep"])
            for i in range(num_uhe):
                equacao += float(corte["Coefs"][i]) * vf[i]
            restricoes.append(alpha[0] >= equacao)

    problema = op(fob, restricoes)
    problema.solve("dense", "glpk")

    if problema.status != "optimal":
        raise RuntimeError(
            f"O despacho do estágio {iest} não encontrou solução ótima: "
            f"status={problema.status}"
        )

    resultado = {
        "DGer": {
            "Déficit": _valor(deficit[0]),
            "CMO": float(restricoes[restricao_demanda].multiplier.value[0]),
            "CustoTotal": float(fob.value()[0]),
            "CustoFuturo": _valor(alpha[0]),
        },
        "UHE": [],
        "UTE": [],
    }

    for i in range(num_uhe):
        resultado["UHE"].append({
            "vf": _valor(vf[i]),
            "vt": _valor(vt[i]),
            "vv": _valor(vv[i]),
            "cma": float(restricoes[i].multiplier.value[0]),
        })

    for i in range(num_ute):
        resultado["UTE"].append({"gt": _valor(gt[i])})

    if imprime:
        print(f"Estágio {iest} | custo total: {resultado['DGer']['CustoTotal']:.2f}")

    return resultado


def pddd(sistema, cenario=0, imprime=False, tolerancia=0.01, max_iteracoes=100):
    """Executa a PDDD para um cenário determinístico de afluências.

    cenario=0 corresponde à primeira coluna de Afl e cenario=1 à segunda.
    """
    if cenario not in range(sistema["DGer"]["Nr_Cen"]):
        raise ValueError("Cenário inválido.")

    inicio = time.time()
    num_uhe = len(sistema["UHE"])
    num_ute = len(sistema["UTE"])
    num_estagios = sistema["DGer"]["Nr_Est"]

    cortes = []
    zinf_historico = []
    zsup_historico = []
    memoria_final = []

    for iteracao in range(1, max_iteracoes + 1):
        # ------------------------------- FORWARD ------------------------------
        memoria = []
        vi_atual = [u["VI"] for u in sistema["UHE"]]
        zsup = 0.0
        zinf = None

        for estagio in range(1, num_estagios + 1):
            afl = [u["Afl"][estagio - 1][cenario] for u in sistema["UHE"]]
            decisao = despacho_pddd(
                sistema, vi_atual, afl, cortes, estagio, imprime
            )
            memoria.append(decisao)
            zsup += decisao["DGer"]["CustoTotal"] - decisao["DGer"]["CustoFuturo"]
            if estagio == 1:
                zinf = decisao["DGer"]["CustoTotal"]
            vi_atual = [u["vf"] for u in decisao["UHE"]]

        zinf_historico.append(float(zinf))
        zsup_historico.append(float(zsup))
        memoria_final = memoria

        if abs(zsup - zinf) <= tolerancia:
            break

        # ------------------------------ BACKWARD -----------------------------
        # Usa o volume inicial efetivamente visitado no forward em cada estágio
        # e a afluência correspondente ao próprio estágio.
        for estagio in range(num_estagios, 0, -1):
            if estagio == 1:
                vi_corte = [u["VI"] for u in sistema["UHE"]]
            else:
                vi_corte = [u["vf"] for u in memoria[estagio - 2]["UHE"]]

            afl = [u["Afl"][estagio - 1][cenario] for u in sistema["UHE"]]
            decisao = despacho_pddd(
                sistema, vi_corte, afl, cortes, estagio, imprime=False
            )

            coefs = [-u["cma"] for u in decisao["UHE"]]
            termo_indep = decisao["DGer"]["CustoTotal"]
            termo_indep -= sum(vi_corte[i] * coefs[i] for i in range(num_uhe))

            # O corte calculado no estágio t é usado como custo futuro em t-1.
            if estagio > 1:
                cortes.append({
                    "Estagio": estagio - 1,
                    "Termo_Indep": float(termo_indep),
                    "Coefs": [float(c) for c in coefs],
                })
    else:
        iteracao = max_iteracoes

    vf = [[] for _ in range(num_uhe)]
    vt = [[] for _ in range(num_uhe)]
    vv = [[] for _ in range(num_uhe)]
    cma = [[] for _ in range(num_uhe)]
    gt = [[] for _ in range(num_ute)]
    cmo = []
    deficit = []
    custo_total = 0.0

    for decisao in memoria_final:
        for i in range(num_uhe):
            vf[i].append(decisao["UHE"][i]["vf"])
            vt[i].append(decisao["UHE"][i]["vt"])
            vv[i].append(decisao["UHE"][i]["vv"])
            cma[i].append(decisao["UHE"][i]["cma"])
        for i in range(num_ute):
            gt[i].append(decisao["UTE"][i]["gt"])
        cmo.append(decisao["DGer"]["CMO"])
        deficit.append(decisao["DGer"]["Déficit"])
        custo_total += decisao["DGer"]["CustoTotal"] - decisao["DGer"]["CustoFuturo"]

    return {
        "DGer": {
            "CustoTotal": float(custo_total),
            "CMO": cmo,
            "Deficit": deficit,
            "ZINF": zinf_historico,
            "ZSUP": zsup_historico,
            "Nr_Iteracoes": len(zinf_historico),
            "Convergiu": abs(zsup_historico[-1] - zinf_historico[-1]) <= tolerancia,
            "Tempo": time.time() - inicio,
        },
        "UHE": [
            {"vf": vf[i], "vt": vt[i], "vv": vv[i], "cma": cma[i]}
            for i in range(num_uhe)
        ],
        "UTE": [{"gt": gt[i]} for i in range(num_ute)],
    }
