"""Execução cronometrada e comparação de Dijkstra e A*."""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import pandas as pd
import networkx as nx

from .algorithms import a_estrela_manual, dijkstra_manual


def avaliar_algoritmos(
    G: nx.DiGraph,
    no_origem: Any,
    no_destino: Any,
    peso: str = "length",
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Executa os algoritmos nas mesmas condições e compara as métricas."""
    resultados: dict[str, dict[str, Any]] = {}
    linhas: list[dict[str, Any]] = []

    for algoritmo in (dijkstra_manual, a_estrela_manual):
        inicio = time.perf_counter()
        resultado = algoritmo(G, no_origem, no_destino, peso=peso)
        tempo_s = time.perf_counter() - inicio

        resultado["tempo_s"] = tempo_s
        resultado["arestas_caminho"] = len(resultado["caminho"]) - 1
        resultados[resultado["algoritmo"]] = resultado
        linhas.append(
            {
                "Algoritmo": resultado["algoritmo"],
                "Distância (m)": resultado["distancia_m"],
                "Tempo (s)": tempo_s,
                "Vértices explorados": resultado["vertices_explorados"],
                "Arestas no caminho": resultado["arestas_caminho"],
            }
        )

    comparacao = pd.DataFrame(linhas).set_index("Algoritmo")
    custo_dijkstra = resultados["Dijkstra"]["distancia_m"]
    custo_astar = resultados["A*"]["distancia_m"]
    if not math.isclose(custo_dijkstra, custo_astar, rel_tol=1e-9, abs_tol=1e-6):
        raise AssertionError(
            "Dijkstra e A* retornaram custos diferentes. Verifique os pesos e "
            "a admissibilidade/consistência da heurística."
        )
    return comparacao, resultados


def salvar_comparacao_csv(
    comparacao: pd.DataFrame, caminho: str | Path
) -> Path:
    """Salva a tabela de avaliação em CSV."""
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    comparacao.to_csv(destino, encoding="utf-8-sig")
    return destino
