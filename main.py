from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from last_mile.algorithms import a_estrela_manual, dijkstra_manual
from last_mile.config import (
    DEFAULT_JSON,
    DEFAULT_MARGIN_M,
    DEFAULT_NETWORK_TYPE,
    DEFAULT_REPETITIONS,
    DEFAULT_RETAIN_ALL,
    DEFAULT_SIMPLIFY,
    DEFAULT_STATION_COORDINATES_CSV,
    DEFAULT_TRUNCATE_BY_EDGE,
    DEFAULT_WEIGHT,
    RESULTS_DIR,
    ensure_project_dirs,
)
from last_mile.data_loader import (
    carregar_registro_amazon,
    listar_paradas_rota,
    listar_rotas_amazon,
)
from last_mile.evaluation import avaliar_algoritmos, salvar_comparacao_csv
from last_mile.geo import associar_coordenadas_a_nos
from last_mile.graph_cache import (
    converter_para_digrafo_ponderado,
    obter_grafo_osm_com_cache,
)
from last_mile.visualization import desenhar_rota


def executar_demo_offline() -> None:
    """Testa a implementação em grafo sintético, sem usar como resultado Amazon."""
    G = nx.DiGraph()
    G.add_node("S", x=-97.70, y=30.39)
    G.add_node("A", x=-97.699, y=30.39)
    G.add_node("B", x=-97.70, y=30.391)
    G.add_node("T", x=-97.698, y=30.39)
    G.add_edge("S", "A", length=120.0)
    G.add_edge("A", "T", length=120.0)
    G.add_edge("S", "B", length=130.0)
    G.add_edge("B", "T", length=300.0)

    d = dijkstra_manual(G, "S", "T")
    a = a_estrela_manual(G, "S", "T")
    print("\n=== DEMONSTRAÇÃO SINTÉTICA (NÃO É RESULTADO AMAZON) ===")
    for resultado in (d, a):
        print(
            f"{resultado['algoritmo']}: caminho={resultado['caminho']}, "
            f"distância={resultado['distancia_m']:.2f} m, "
            f"vértices explorados={resultado['vertices_explorados']}"
        )
    if not abs(d["distancia_m"] - a["distancia_m"]) <= 1e-6:
        raise AssertionError("Os algoritmos deveriam encontrar o mesmo custo.")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compara Dijkstra e A* em uma rota do dataset oficial Amazon e na malha OSM."
    )
    parser.add_argument(
        "--json", type=Path, default=DEFAULT_JSON,
        help=f"Caminho do route_data.json oficial (padrão: {DEFAULT_JSON}).",
    )
    parser.add_argument("--route-id", default=None, help="RouteID que será analisado.")
    parser.add_argument(
        "--destination-stop", default=None,
        help="ID de uma única parada Dropoff da rota escolhida.",
    )
    parser.add_argument(
        "--origin-coordinates", nargs=2, type=float, metavar=("LATITUDE", "LONGITUDE"),
        help="Coordenadas verificadas da estação; têm precedência sobre a parada Station e o CSV.",
    )
    parser.add_argument(
        "--station-coordinates-csv", type=Path, default=DEFAULT_STATION_COORDINATES_CSV,
        help="CSV auxiliar station_code,latitude,longitude (padrão: data/station_coordinates.csv).",
    )
    parser.add_argument(
        "--list-routes", action="store_true",
        help="Lista rotas disponíveis no route_data.json e encerra.",
    )
    parser.add_argument(
        "--list-stops", action="store_true",
        help="Lista paradas e coordenadas da rota informada por --route-id e encerra.",
    )
    parser.add_argument("--limit", type=int, default=30, help="Máximo de rotas exibidas com --list-routes.")
    parser.add_argument(
        "--network-type",
        choices=("drive", "drive_service", "walk", "bike", "all", "all_public"),
        default=DEFAULT_NETWORK_TYPE,
        help="Tipo de rede OpenStreetMap (padrão: drive).",
    )
    parser.add_argument("--margin-m", type=float, default=DEFAULT_MARGIN_M,
                        help="Margem do recorte OSM em metros (padrão: 1500).")
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS,
                        help="Medições cronometradas por algoritmo (padrão: 10).")
    parser.add_argument("--rebuild-cache", action="store_true",
                        help="Ignora o GraphML local e consulta novamente o OpenStreetMap.")
    parser.add_argument("--no-show", action="store_true",
                        help="Salva mapas sem abrir janelas de visualização.")
    parser.add_argument("--demo", action="store_true",
                        help="Executa um pequeno teste sintético offline; não usa dados Amazon.")
    parser.add_argument(
        "--trace", type=int, default=0, metavar="N",
        help="Mostra os N primeiros passos de cada algoritmo (extrações e relaxamentos); 0 desativa.",
    )
    return parser


def criar_argumentos() -> argparse.Namespace:
    return construir_parser().parse_args()


def _formatar_metros(valor: float) -> str:
    """Formata distâncias em metros, usando o símbolo de infinito quando preciso."""
    if math.isinf(valor):
        return "infinito"
    return f"{valor:,.2f} m"


def _imprimir_trace(
    G: nx.DiGraph, origem: Any, destino: Any, limite: int
) -> None:
    """Executa cada algoritmo com registro e imprime os primeiros passos."""
    for funcao, nome in ((dijkstra_manual, "Dijkstra"), (a_estrela_manual, "A*")):
        eventos: list[dict[str, Any]] = []
        funcao(G, origem, destino, peso=DEFAULT_WEIGHT, registrar=eventos.append)
        print(f"\n=== PRIMEIROS PASSOS — {nome} ({len(eventos)} eventos registrados) ===")
        for evento in eventos[:limite]:
            if evento["evento"] == "extrai":
                linha = (
                    f"  extrai {evento['no']} | g={_formatar_metros(evento['dist'])}"
                )
                if "f" in evento:
                    linha += f" | f={_formatar_metros(evento['f'])}"
                print(f"{linha} | fila={evento['fila']}")
            else:
                print(
                    f"  relaxa {evento['de']}->{evento['para']} | peso="
                    f"{_formatar_metros(evento['peso'])} | "
                    f"{_formatar_metros(evento['antes'])} -> "
                    f"{_formatar_metros(evento['depois'])}"
                )
        if len(eventos) > limite:
            print(f"  ... ({len(eventos) - limite} eventos omitidos)")


def _salvar_metadados_execucao(
    registro: dict[str, Any],
    associacoes: pd.DataFrame,
    comparacao: pd.DataFrame,
    caminho: Path,
    fonte_grafo: str,
) -> None:
    payload = {
        "fonte_dados": "Amazon Last Mile Routing Research Challenge / route_data.json",
        "route_id": registro["route_id"],
        "station_code": registro["station_code"],
        "data_rota": registro["metadados"].get("date"),
        "origem": registro["origem"],
        "origem_fonte": registro["origem_fonte"],
        "destino": registro["destino"],
        "origem_do_grafo_osm": fonte_grafo,
        "associacoes_osm": associacoes.to_dict(orient="records"),
        "comparacao": comparacao.reset_index().to_dict(orient="records"),
        "observacao": (
            "Coordenadas Amazon são anonimizadas/perturbadas. A origem pode vir de "
            "uma parada Station do registro ou de coordenadas externas verificadas."
        ),
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(payload, arquivo, ensure_ascii=False, indent=2, default=str)


def main() -> None:
    if len(sys.argv) == 1:
        construir_parser().print_help()
        return
    args = criar_argumentos()
    if args.demo:
        executar_demo_offline()
        return

    ensure_project_dirs()
    if not args.json.is_file():
        raise FileNotFoundError(
            f"Não encontrei {args.json}. Baixe somente o arquivo oficial de rotas com:\n"
            "  python download_amazon_data.py --split training\n"
            "Depois execute novamente com --list-routes."
        )

    if args.list_routes:
        rotas = listar_rotas_amazon(args.json, limite=args.limit if args.limit > 0 else None)
        print("\n=== ROTAS AMAZON DISPONÍVEIS ===")
        print(rotas.to_string(index=False))
        print("\nUse --route-id para escolher uma rota e --list-stops para consultar seus clientes.")
        return

    if args.list_stops:
        if not args.route_id:
            raise ValueError("Informe --route-id ao utilizar --list-stops.")
        paradas = listar_paradas_rota(args.json, args.route_id)
        print(f"\n=== PARADAS DA ROTA {args.route_id} ===")
        print(paradas.to_string(index=False))
        return

    if not args.route_id:
        raise ValueError(
            "Informe --route-id. Primeiro execute: python main.py --list-routes"
        )

    coordenadas_estacao = tuple(args.origin_coordinates) if args.origin_coordinates else None
    registro = carregar_registro_amazon(
        fonte_json=args.json,
        route_id=args.route_id,
        stop_id_destino=args.destination_stop,
        coordenadas_estacao=coordenadas_estacao,
        station_coordinates_csv=args.station_coordinates_csv,
    )

    print("\n=== ROTA REAL SELECIONADA ===")
    print(f"Fonte: {args.json}")
    print(f"RouteID: {registro['route_id']}")
    print(f"Station code: {registro['station_code']}")
    print(f"Data da rota: {registro['metadados'].get('date')}")
    print(f"Origem: {registro['origem']} ({registro['origem_fonte']})")
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
        f"\nOrigem do grafo: {metadados_cache.get('fonte')} | "
        f"Nós: {G_osm.number_of_nodes():,} | Arestas: {G_osm.number_of_edges():,}"
    )

    no_origem, no_destino, associacoes = associar_coordenadas_a_nos(
        G_osm, registro["origem"], registro["destino"]
    )
    print("\n=== ASSOCIAÇÃO DAS COORDENADAS AOS NÓS OSM ===")
    print(associacoes.to_string(index=False))

    G = converter_para_digrafo_ponderado(G_osm, peso=DEFAULT_WEIGHT)
    print(
        f"\nGrafo direcionado ponderado: {G.number_of_nodes():,} vértices e "
        f"{G.number_of_edges():,} arestas."
    )

    comparacao, resultados = avaliar_algoritmos(
        G, no_origem, no_destino,
        peso=DEFAULT_WEIGHT,
        repeticoes=args.repetitions,
    )
    print("\n=== COMPARAÇÃO DOS ALGORITMOS ===")
    print(comparacao.to_string(float_format=lambda valor: f"{valor:,.8f}"))

    if args.trace > 0:
        _imprimir_trace(G, no_origem, no_destino, args.trace)

    csv_path = salvar_comparacao_csv(
        comparacao, RESULTS_DIR / "comparacao_algoritmos_amazon_osm.csv"
    )
    mapas: list[Path] = []
    for nome, resultado in resultados.items():
        nome_arquivo = "rota_dijkstra.png" if nome == "Dijkstra" else "rota_astar.png"
        titulo = (
            f"{nome} | RouteID {registro['route_id']} | "
            f"{resultado['distancia_m']:,.1f} m"
        )
        mapas.append(desenhar_rota(
            G_osm=G_osm,
            caminho=resultado["caminho"],
            origem=registro["origem"],
            destino=registro["destino"],
            arquivo_saida=RESULTS_DIR / nome_arquivo,
            titulo=titulo,
            mostrar=not args.no_show,
        ))

    metadata_path = RESULTS_DIR / "execucao_amazon_osm.json"
    _salvar_metadados_execucao(
        registro, associacoes, comparacao, metadata_path, metadados_cache.get("fonte", "desconhecida")
    )

    print("\n=== ARQUIVOS GERADOS ===")
    print(f"Comparação CSV: {csv_path}")
    for mapa in mapas:
        print(f"Mapa: {mapa}")
    print(f"Metadados: {metadata_path}")
    print("Cache do grafo: cache/osm_graphs/*.graphml")


if __name__ == "__main__":
    main()
