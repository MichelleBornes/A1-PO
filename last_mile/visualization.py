"""Visualização da rota calculada sobre a malha viária OSM."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def desenhar_rota(
    G_osm: Any,
    caminho: list[Any],
    origem: dict[str, float],
    destino: dict[str, float],
    arquivo_saida: str | Path,
    titulo: str = "Rota otimizada com A*",
    mostrar: bool = True,
) -> Path:
    """Plota e salva a rota no grafo original do OSMnx (MultiDiGraph)."""
    import matplotlib.pyplot as plt
    import osmnx as ox

    if not caminho:
        raise ValueError("O caminho está vazio; não há rota para desenhar.")

    caminho_saida = Path(arquivo_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = ox.plot.plot_graph_route(
        G_osm,
        caminho,
        route_color="#d62728",
        route_linewidth=4,
        node_size=0,
        bgcolor="white",
        show=False,
        close=False,
    )
    no_inicio, no_fim = caminho[0], caminho[-1]
    ax.scatter(
        G_osm.nodes[no_inicio]["x"],
        G_osm.nodes[no_inicio]["y"],
        s=75,
        marker="o",
        label="Origem associada",
        zorder=5,
    )
    ax.scatter(
        G_osm.nodes[no_fim]["x"],
        G_osm.nodes[no_fim]["y"],
        s=100,
        marker="*",
        label="Destino associado",
        zorder=5,
    )
    # Marca também as coordenadas originais, para evidenciar o ajuste (snap)
    # da posição geográfica ao nó viário mais próximo.
    ax.scatter(
        float(origem["lon"]), float(origem["lat"]),
        s=55, marker="x", label="Coordenada de origem", zorder=6,
    )
    ax.scatter(
        float(destino["lon"]), float(destino["lat"]),
        s=55, marker="x", label="Coordenada de destino", zorder=6,
    )
    ax.set_title(titulo)
    ax.legend()
    fig.savefig(caminho_saida, dpi=180, bbox_inches="tight")

    if mostrar:
        plt.show()
    plt.close(fig)
    return caminho_saida
