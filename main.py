from __future__ import annotations

import argparse
from pathlib import Path

import networkx as nx

from last_mile.algorithms import a_estrela_manual, dijkstra_manual
from last_mile.config import (
    DEFAULT_JSON,
    DEFAULT_MARGIN_M,
    DEFAULT_NETWORK_TYPE,
    DEFAULT_RETAIN_ALL,
    DEFAULT_SIMPLIFY,
    DEFAULT_TRUNCATE_BY_EDGE,
    DEFAULT_WEIGHT,
    RESULTS_DIR,
    ensure_project_dirs,
)
from last_mile.data_loader import carregar_registro_amazon
from last_mile.evaluation import avaliar_algoritmos, salvar_comparacao_csv
from last_mile.geo import associar_coordenadas_a_nos
from last_mile.graph_cache import (
    converter_para_digrafo_ponderado,
    obter_grafo_osm_com_cache,
)
from last_mile.visualization import desenhar_rota


def executar_demo_offline() -> None:
    """Testa os algoritmos sem conexão com a internet ou download OSM."""
    G = nx.DiGraph()
    G.add_node("S", x=0.000, y=0.000)
    G.add_node("A", x=0.001, y=0.000)
    G.add_node("B", x=0.000, y=0.001)
    G.add_node("T", x=0.002, y=0.000)
    G.add_edge("S", "A", length=120.0)
    G.add_edge("A", "T", length=120.0)
    G.add_edge("S", "B", length=130.0)
    G.add_edge("B", "T", length=300.0)

    resultado_dijkstra = dijkstra_manual(G, "S", "T")
    resultado_astar = a_estrela_manual(G, "S", "T")
    print("\n=== TESTE OFFLINE ===")
    for resultado in (resultado_dijkstra, resultado_astar):
        print(
            f"{resultado['algoritmo']}: caminho={resultado['caminho']}, "
            f"distância={resultado['distancia_m']:.2f} m, "
            f"vértices explorados={resultado['vertices_explorados']}"
        )
    if abs(resultado_dijkstra["distancia_m"] - resultado_astar["distancia_m"]) > 1e-6:
        raise AssertionError("Os algoritmos deveriam encontrar o mesmo custo.")
    print("\nOs dois algoritmos encontraram o mesmo custo mínimo.")


def criar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara Dijkstra e A* em uma malha viária real do OpenStreetMap."
    )
    parser.add_argument("--demo", action="store_true", help="Executa teste offline sintético.")
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON,
        help=f"Caminho para route_data.json (padrão: {DEFAULT_JSON}).",
    )
    parser.add_argument("--route-id", default=None, help="ID da rota no JSON da Amazon.")
    parser.add_argument(
        "--destination-stop",
        default=None,
        help="ID da parada Dropoff; pode ser omitido se houver apenas uma.",
    )
    parser.add_argument(
        "--origin-coordinates",
        nargs=2,
        type=float,
        metavar=("LATITUDE", "LONGITUDE"),
        help="Coordenadas da estação quando não houver parada Station no registro.",
    )
    parser.add_argument(
        "--network-type",
        choices=("drive", "drive_service", "walk", "bike", "all", "all_public"),
        default=DEFAULT_NETWORK_TYPE,
        help="Tipo de rede OSM a consultar (padrão: drive).",
    )
    parser.add_argument(
        "--margin-m",
        type=float,
        default=DEFAULT_MARGIN_M,
        help="Margem em metros ao redor dos extremos da rota (padrão: 1500).",
    )
    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Ignora o GraphML local e consulta novamente o OpenStreetMap.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Salva o mapa sem abrir janela interativa.",
    )
    return parser.parse_args()


def main() -> None:
    args = criar_argumentos()
    if args.demo:
        executar_demo_offline()
        return

    ensure_project_dirs()
    coordenadas_estacao = tuple(args.origin_coordinates) if args.origin_coordinates else None
    registro = carregar_registro_amazon(
        fonte_json=args.json,
        route_id=args.route_id,
        stop_id_destino=args.destination_stop,
        coordenadas_estacao=coordenadas_estacao,
    )

    print("\n=== REGISTRO SELECIONADO ===")
    print(f"Rota: {registro['route_id']}")
    print(f"Station code: {registro['station_code']}")
    print(f"Origem: {registro['origem']}")
    print(f"Destino: {registro['destino']}")

    G_osm, metadados_cache = obter_grafo_osm_com_cache(
        origem=registro["origem"],
        destino=registro["destino"],
        margem_m=args.margin_m,
        network_type=args.network_type,
        simplify=DEFAULT_SIMPLIFY,
        retain_all=DEFAULT_RETAIN_ALL,
        truncate_by_edge=DEFAULT_TRUNCATE_BY_EDGE,
        force_download=args.rebuild_cache,
    )
    print(
        f"Origem do grafo: {metadados_cache.get('fonte')} | "
        f"Nós: {G_osm.number_of_nodes():,} | "
        f"Arestas: {G_osm.number_of_edges():,}"
    )

    no_origem, no_destino, associacoes = associar_coordenadas_a_nos(
        G_osm, registro["origem"], registro["destino"]
    )
    print("\n=== ASSOCIAÇÃO AOS NÓS OSM ===")
    print(associacoes.to_string(index=False))

    G = converter_para_digrafo_ponderado(G_osm, peso=DEFAULT_WEIGHT)
    print(
        f"\nGrafo direcionado ponderado: {G.number_of_nodes():,} vértices e "
        f"{G.number_of_edges():,} arestas."
    )

    comparacao, resultados = avaliar_algoritmos(
        G, no_origem, no_destino, peso=DEFAULT_WEIGHT
    )
    print("\n=== COMPARAÇÃO DOS ALGORITMOS ===")
    print(comparacao.to_string(float_format=lambda valor: f"{valor:,.6f}"))

    arquivo_csv = salvar_comparacao_csv(
        comparacao, RESULTS_DIR / "comparacao_algoritmos.csv"
    )
    arquivo_mapa = desenhar_rota(
        G_osm=G_osm,
        caminho=resultados["A*"]["caminho"],
        origem=registro["origem"],
        destino=registro["destino"],
        arquivo_saida=RESULTS_DIR / "rota_astar.png",
        titulo=(
            f"Rota A* — {resultados['A*']['distancia_m']:,.0f} m | "
            f"{resultados['A*']['arestas_caminho']} arestas"
        ),
        mostrar=not args.no_show,
    )

    print("\n=== ARQUIVOS GERADOS ===")
    print(f"Tabela CSV: {arquivo_csv}")
    print(f"Mapa: {arquivo_mapa}")
    print("Cache do grafo: cache/osm_graphs/*.graphml")
    print("Para atualizar a rede OSM, execute novamente com --rebuild-cache.")


if __name__ == "__main__":
    main()
