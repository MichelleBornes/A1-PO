"""Implementações didáticas de Dijkstra e A* para grafos direcionados."""
from __future__ import annotations

import heapq
import math
from itertools import count
from typing import Any, Callable

import networkx as nx

from .geo import distancia_haversine_m


def reconstruir_caminho(
    predecessores: dict[Any, Any], origem: Any, destino: Any
) -> list[Any] | None:
    """Reconstrói a sequência de nós a partir do dicionário de predecessores."""
    if origem == destino:
        return [origem]
    if destino not in predecessores:
        return None

    caminho = [destino]
    atual = destino
    while atual != origem:
        atual = predecessores.get(atual)
        if atual is None:
            return None
        caminho.append(atual)
    caminho.reverse()
    return caminho


def dijkstra_manual(
    G: nx.DiGraph, origem: Any, destino: Any, peso: str = "length"
) -> dict[str, Any]:
    """Calcula o caminho mínimo com Dijkstra e contabiliza nós finalizados.

    Um vértice é considerado explorado quando sai da fila de prioridade com
    seu menor custo confirmado. O destino é contado quando é retirado da fila.
    Pesos negativos não são permitidos.
    """
    if origem not in G or destino not in G:
        raise nx.NodeNotFound("Origem ou destino não pertence ao grafo.")

    distancias = {origem: 0.0}
    predecessores: dict[Any, Any] = {}
    finalizados: set[Any] = set()
    explorados = 0
    sequencia = count()
    fila = [(0.0, next(sequencia), origem)]

    while fila:
        distancia_atual, _, u = heapq.heappop(fila)
        if u in finalizados or distancia_atual > distancias.get(u, math.inf):
            continue

        finalizados.add(u)
        explorados += 1
        if u == destino:
            break

        for v, atributos in G[u].items():
            if peso not in atributos:
                raise KeyError(f"A aresta ({u}, {v}) não possui o peso '{peso}'.")
            custo_aresta = float(atributos[peso])
            if not math.isfinite(custo_aresta) or custo_aresta < 0:
                raise ValueError("Dijkstra exige pesos finitos e não negativos.")
            if v in finalizados:
                continue

            nova_distancia = distancia_atual + custo_aresta
            if nova_distancia < distancias.get(v, math.inf):
                distancias[v] = nova_distancia
                predecessores[v] = u
                heapq.heappush(fila, (nova_distancia, next(sequencia), v))

    caminho = reconstruir_caminho(predecessores, origem, destino)
    if caminho is None:
        raise nx.NetworkXNoPath(
            f"Não existe caminho direcionado entre {origem} e {destino}."
        )

    return {
        "algoritmo": "Dijkstra",
        "caminho": caminho,
        "distancia_m": float(distancias[destino]),
        "vertices_explorados": explorados,
    }


def heuristica_haversine(
    G: nx.DiGraph, no: Any, destino: Any
) -> float:
    """Estima o custo restante em linha reta (metros) usando lat/lon dos nós."""
    dados_no = G.nodes[no]
    dados_destino = G.nodes[destino]
    return distancia_haversine_m(
        float(dados_no["y"]),
        float(dados_no["x"]),
        float(dados_destino["y"]),
        float(dados_destino["x"]),
    )


def a_estrela_manual(
    G: nx.DiGraph,
    origem: Any,
    destino: Any,
    peso: str = "length",
    heuristica: Callable[[nx.DiGraph, Any, Any], float] = heuristica_haversine,
) -> dict[str, Any]:
    """Calcula o caminho mínimo com A* e heurística geográfica admissível.

    Para a heurística Haversine, os pesos devem representar comprimentos reais
    em metros e satisfazer h(u) <= custo(u,v) + h(v). Essa condição decorre da
    desigualdade triangular quando cada `length` não é menor que a distância
    geodésica entre os nós extremos da aresta. Se forem usados pesos artificiais,
    use uma heurística nula ou outra heurística demonstravelmente admissível.
    """
    if origem not in G or destino not in G:
        raise nx.NodeNotFound("Origem ou destino não pertence ao grafo.")

    g_score = {origem: 0.0}
    predecessores: dict[Any, Any] = {}
    finalizados: set[Any] = set()
    explorados = 0
    sequencia = count()
    h_origem = float(heuristica(G, origem, destino))
    fila = [(h_origem, next(sequencia), 0.0, origem)]

    while fila:
        _, _, g_atual, u = heapq.heappop(fila)
        if u in finalizados or g_atual > g_score.get(u, math.inf):
            continue

        finalizados.add(u)
        explorados += 1
        if u == destino:
            break

        for v, atributos in G[u].items():
            if peso not in atributos:
                raise KeyError(f"A aresta ({u}, {v}) não possui o peso '{peso}'.")
            custo_aresta = float(atributos[peso])
            if not math.isfinite(custo_aresta) or custo_aresta < 0:
                raise ValueError("A* exige pesos finitos e não negativos.")
            if v in finalizados:
                continue

            tentativa_g = g_atual + custo_aresta
            if tentativa_g < g_score.get(v, math.inf):
                g_score[v] = tentativa_g
                predecessores[v] = u
                h_v = float(heuristica(G, v, destino))
                if not math.isfinite(h_v) or h_v < 0:
                    raise ValueError("A heurística deve retornar um valor finito e >= 0.")
                heapq.heappush(
                    fila,
                    (tentativa_g + h_v, next(sequencia), tentativa_g, v),
                )

    caminho = reconstruir_caminho(predecessores, origem, destino)
    if caminho is None:
        raise nx.NetworkXNoPath(
            f"Não existe caminho direcionado entre {origem} e {destino}."
        )

    return {
        "algoritmo": "A*",
        "caminho": caminho,
        "distancia_m": float(g_score[destino]),
        "vertices_explorados": explorados,
    }
