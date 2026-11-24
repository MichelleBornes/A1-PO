"""Execução cronometrada e comparação estatística de Dijkstra e A*."""
from __future__ import annotations

import math
import statistics
import time
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from .algorithms import a_estrela_manual, dijkstra_manual


def avaliar_algoritmos(
    G: nx.DiGraph,
    no_origem: Any,
    no_destino: Any,
    peso: str = "length",
    repeticoes: int = 10,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Compara os algoritmos usando a mediana de várias medições.

    Uma chamada de aquecimento por algoritmo é descartada. O tempo medido
    considera somente a busca, sem download OSM, conversão ou visualização.
    """
    if repeticoes < 1:
        raise ValueError("repeticoes deve ser pelo menos 1.")

    algoritmos = (dijkstra_manual, a_estrela_manual)
    for algoritmo in algoritmos:
        algoritmo(G, no_origem, no_destino, peso=peso)  # aquecimento não cronometrado

    resultados: dict[str, dict[str, Any]] = {}
    linhas: list[dict[str, Any]] = []

    for algoritmo in algoritmos:
        tempos: list[float] = []
        ultimo_resultado: dict[str, Any] | None = None
        for _ in range(repeticoes):
            inicio = time.perf_counter()
            ultimo_resultado = algoritmo(G, no_origem, no_destino, peso=peso)
            tempos.append(time.perf_counter() - inicio)

        assert ultimo_resultado is not None
        ultimo_resultado["tempo_mediano_s"] = statistics.median(tempos)
        ultimo_resultado["tempo_medio_s"] = statistics.mean(tempos)
        ultimo_resultado["tempos_s"] = tempos
        ultimo_resultado["repeticoes"] = repeticoes
        ultimo_resultado["arestas_caminho"] = len(ultimo_resultado["caminho"]) - 1
        resultados[ultimo_resultado["algoritmo"]] = ultimo_resultado

        linhas.append({
            "Algoritmo": ultimo_resultado["algoritmo"],
            "Distância (m)": ultimo_resultado["distancia_m"],
            "Tempo mediano (s)": statistics.median(tempos),
            "Tempo médio (s)": statistics.mean(tempos),
            "Vértices explorados": ultimo_resultado["vertices_explorados"],
            "Arestas no caminho": ultimo_resultado["arestas_caminho"],
            "Repetições": repeticoes,
        })

    comparacao = pd.DataFrame(linhas).set_index("Algoritmo")
    custo_dijkstra = resultados["Dijkstra"]["distancia_m"]
    custo_astar = resultados["A*"]["distancia_m"]
    if not math.isclose(custo_dijkstra, custo_astar, rel_tol=1e-9, abs_tol=1e-6):
        raise AssertionError(
            "Dijkstra e A* retornaram custos diferentes. Verifique os pesos e "
            "a admissibilidade/consistência da heurística."
        )
    return comparacao, resultados


def salvar_comparacao_csv(comparacao: pd.DataFrame, caminho: str | Path) -> Path:
    """Salva a tabela de avaliação em CSV."""
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    comparacao.to_csv(destino, encoding="utf-8-sig")
    return destino
