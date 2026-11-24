from __future__ import annotations

import math
from typing import Any

import pandas as pd


def distancia_haversine_m(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    raio_terra_m = 6_371_009.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    return 2 * raio_terra_m * math.asin(math.sqrt(a))


def associar_coordenadas_a_nos(
    G_osm: Any,
    origem: dict[str, float],
    destino: dict[str, float],
) -> tuple[Any, Any, pd.DataFrame]:
    import osmnx as ox

    try:
        no_origem, distancia_origem = ox.distance.nearest_nodes(
            G_osm,
            X=float(origem["lon"]),
            Y=float(origem["lat"]),
            return_dist=True,
        )
        no_destino, distancia_destino = ox.distance.nearest_nodes(
            G_osm,
            X=float(destino["lon"]),
            Y=float(destino["lat"]),
            return_dist=True,
        )
    except ImportError as exc:
        if "scikit-learn" in str(exc).lower() or "balltree" in str(exc).lower():
            raise ImportError(
                "O OSMnx precisa do scikit-learn para localizar nós em um grafo "
                "não projetado. No terminal do VS Code, com a .venv ativada, "
                "execute: python -m pip install 'scikit-learn>=1.7.2,<2.0'. "
                "Ou instale todas as dependências com: "
                "python -m pip install -r requirements.txt"
            ) from exc
        raise

    associacoes = pd.DataFrame(
        [
            {
                "Ponto": "Origem",
                "Nó OSM": no_origem,
                "Afastamento até o nó (m)": float(distancia_origem),
            },
            {
                "Ponto": "Destino",
                "Nó OSM": no_destino,
                "Afastamento até o nó (m)": float(distancia_destino),
            },
        ]
    )
    return no_origem, no_destino, associacoes
