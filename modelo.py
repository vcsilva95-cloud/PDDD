# -*- coding: utf-8 -*-
"""PDDD determinística baseada no código do PDF Codigo_5 - otimista.

Este módulo foi organizado para ser importado pelo app.py do dashboard.
A execução do modelo só ocorre quando a função pddd(...) é chamada.
"""

import time
import numpy as np
from cvxopt.modeling import variable, op


# -----------------------------------------------------------------------------
# DADOS DO SISTEMA
# -----------------------------------------------------------------------------
sistema = {
    "UHE": [
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
    ],
    "UTE": [
        {"Nome": "UTE_Termobahia", "Capac": 186.0, "Custo": 424080.0},
        {"Nome": "UTE_Pecém_II", "Capac": 144.0, "Custo": 1764000.0},
    ],
    "DGer": {
        "CDef": 5969520.0,
        "Carga": [530.0, 508.0, 516.0, 437.0, 420.0, 401.0,
                  390.0, 411.0, 454.0, 490.0, 506.0, 504.0],
        "Nr_Disc": 3,
        "Nr_Est": 12,
        "Nr_Cen": 2,
    },
}


def _escalar(expressao):
    """Converte o valor escalar retornado pelo CVXOPT para float."""
    return float(expressao.value()[0])


def despacho_pddd(sistema, VI, AFL, pote_de_corte, iest, imprime=False):
    """Resolve o problema linear de um estágio.

    Parameters
    ----------
    iest : int
        Número acadêmico do estágio: 1, 2, ..., Nr_Est.
    """
    num_uhe = len(sistema["UHE"])
    num_ute = len(sistema["UTE"])

    vf = variable(num_uhe, "Volume Final na Usina")
    vt = variable(num_uhe, "Volume Turbinado na Usina")
    vv = variable(num_uhe, "Volume Vertido na Usina")
    gt = variable(num_ute, "Geração na Usina Térmica")
    deficit = variable(1, "Déficit de Energia no Sistema")
    alpha = variable(1, "Custo Futuro")

    # Função objetivo: custo imediato + aproximação do custo futuro.
    fob = sum(ute["Custo"] * gt[i] for i, ute in enumerate(sistema["UTE"]))
    fob += sistema["DGer"]["CDef"] * deficit[0]
    fob += sum(0.01 * vv[i] for i in range(num_uhe))
    fob += alpha[0]

    restricoes = []

    # As primeiras num_uhe restrições são os balanços hídricos.
    for i in range(num_uhe):
        restricoes.append(
            vf[i] == float(VI[i]) + float(AFL[i]) - vt[i] - vv[i]
        )

    # A restrição seguinte é o atendimento à demanda.
    atendimento = sum(
        uhe["Prod"] * vt[i] for i, uhe in enumerate(sistema["UHE"])
    )
    atendimento += sum(gt[i] for i in range(num_ute))
    atendimento += deficit[0]
    indice_demanda = len(restricoes)
    restricoes.append(atendimento == sistema["DGer"]["Carga"][iest - 1])

    # Canalizações.
    for i, uhe in enumerate(sistema["UHE"]):
        restricoes += [
            vf[i] >= uhe["Vmin"],
            vf[i] <= uhe["Vmax"],
            vt[i] >= 0,
            vt[i] <= uhe["Engol"],
            vv[i] >= 0,
        ]

    for i, ute in enumerate(sistema["UTE"]):
        restricoes += [gt[i] >= 0, gt[i] <= ute["Capac"]]

    restricoes += [deficit[0] >= 0, alpha[0] >= 0]

    # Cortes da função de custo futuro associados ao estágio corrente.
    for corte in pote_de_corte:
        if corte["Estagio"] == iest:
            equacao = float(corte["Termo_Indep"])
            equacao += sum(
                float(corte["Coefs"][i]) * vf[i] for i in range(num_uhe)
            )
            restricoes.append(alpha[0] >= equacao)

    problema = op(fob, restricoes)
    problema.solve("dense", "glpk")

    if problema.status != "optimal":
        raise RuntimeError(
            f"O estágio {iest} não encontrou solução ótima: {problema.status}"
        )

    dual_balanco = [
        float(restricoes[i].multiplier.value[0]) for i in range(num_uhe)
    ]
    dual_demanda = float(restricoes[indice_demanda].multiplier.value[0])

    resultado = {
        "DGer": {
            "Déficit": _escalar(deficit[0]),
            "CMO": dual_demanda,
            "CustoTotal": float(fob.value()[0]),
            "CustoFuturo": _escalar(alpha[0]),
        },
        "UHE": [
            {
                "vf": _escalar(vf[i]),
                "vt": _escalar(vt[i]),
                "vv": _escalar(vv[i]),
                "cma": dual_balanco[i],
            }
            for i in range(num_uhe)
        ],
        "UTE": [{"gt": _escalar(gt[i])} for i in range(num_ute)],
    }

    if imprime:
        print(f"Estágio {iest} | custo total: {resultado['DGer']['CustoTotal']:.2f}")

    return resultado


def pddd(sistema, cenario=0, imprime=False, tolerancia=0.01, max_iter=100):
    """Executa a Programação Dinâmica Dual Determinística.

    O cenário é uma trajetória determinística escolhida antes da execução:
    0 = otimista; 1 = pessimista.
    """
    num_uhe = len(sistema["UHE"])
    num_ute = len(sistema["UTE"])
    num_est = sistema["DGer"]["Nr_Est"]

    if cenario < 0 or cenario >= sistema["DGer"]["Nr_Cen"]:
        raise ValueError("Cenário inválido. Use 0 para otimista ou 1 para pessimista.")

    pote_de_corte = []
    zinf_hist = []
    zsup_hist = []
    inicio = time.time()
    memoria = None

    for iteracao in range(max_iter):
        # ------------------------------------------------------------------
        # FORWARD: simula a política ao longo dos 12 estágios.
        # ------------------------------------------------------------------
        memoria = []
        vi = [uhe["VI"] for uhe in sistema["UHE"]]
        zsup = 0.0

        for idx_est in range(num_est):
            iest = idx_est + 1
            afl = [uhe["Afl"][idx_est][cenario] for uhe in sistema["UHE"]]
            resultado = despacho_pddd(
                sistema, vi, afl, pote_de_corte, iest, imprime
            )
            memoria.append(resultado)
            zsup += (
                resultado["DGer"]["CustoTotal"]
                - resultado["DGer"]["CustoFuturo"]
            )
            vi = [resultado["UHE"][i]["vf"] for i in range(num_uhe)]

        # O valor do primeiro estágio com alpha é o limite inferior.
        zinf = memoria[0]["DGer"]["CustoTotal"]
        zinf_hist.append(zinf)
        zsup_hist.append(zsup)

        if imprime:
            print(
                f"Iteração {iteracao + 1}: "
                f"ZINF={zinf:.2f} | ZSUP={zsup:.2f} | gap={abs(zsup-zinf):.6f}"
            )

        if abs(zsup - zinf) <= tolerancia:
            break

        # ------------------------------------------------------------------
        # BACKWARD: do último estágio até o segundo.
        # A solução do estágio t produz um corte para alpha do estágio t-1.
        # ------------------------------------------------------------------
        for idx_est in range(num_est - 1, 0, -1):
            iest = idx_est + 1

            # Estado que entra no estágio corrente: vf do estágio anterior
            # visitado na passada forward desta iteração.
            vi = [memoria[idx_est - 1]["UHE"][i]["vf"] for i in range(num_uhe)]
            afl = [uhe["Afl"][idx_est][cenario] for uhe in sistema["UHE"]]

            resultado_bw = despacho_pddd(
                sistema, vi, afl, pote_de_corte, iest, imprime=False
            )

            # Mantém a convenção do código do PDF: coeficiente = -CMA.
            coefs = [-resultado_bw["UHE"][i]["cma"] for i in range(num_uhe)]
            termo_indep = resultado_bw["DGer"]["CustoTotal"]
            termo_indep -= sum(vi[i] * coefs[i] for i in range(num_uhe))

            pote_de_corte.append(
                {
                    "Estagio": iest - 1,
                    "Termo_Indep": termo_indep,
                    "Coefs": coefs,
                }
            )
    else:
        raise RuntimeError(
            f"A PDDD não convergiu em {max_iter} iterações. "
            "Revise os dados ou aumente max_iter."
        )

    # Séries no formato consumido pelo app.py.
    vf = [[d["UHE"][i]["vf"] for d in memoria] for i in range(num_uhe)]
    vt = [[d["UHE"][i]["vt"] for d in memoria] for i in range(num_uhe)]
    vv = [[d["UHE"][i]["vv"] for d in memoria] for i in range(num_uhe)]

    # O app apresenta o valor da água como o negativo do dual bruto,
    # seguindo a mesma convenção usada na formação dos cortes do PDF.
    cma = [[-d["UHE"][i]["cma"] for d in memoria] for i in range(num_uhe)]
    gt = [[d["UTE"][i]["gt"] for d in memoria] for i in range(num_ute)]

    return {
        "DGer": {
            "CustoTotal": zsup_hist[-1],
            "CMO": [-d["DGer"]["CMO"] for d in memoria],
            "Deficit": [d["DGer"]["Déficit"] for d in memoria],
            "ZINF": zinf_hist,
            "ZSUP": zsup_hist,
            "Nr_Iteracoes": len(zinf_hist),
            "Tempo": time.time() - inicio,
        },
        "UHE": [
            {"vf": vf[i], "vt": vt[i], "vv": vv[i], "cma": cma[i]}
            for i in range(num_uhe)
        ],
        "UTE": [{"gt": gt[i]} for i in range(num_ute)],
    }
