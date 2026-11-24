from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import GRAPH_CACHE_DIR, ensure_project_dirs
from .geo import distancia_haversine_m


def _parametros_consulta(
    origem: dict[str, float],
    destino: dict[str, float],
    margem_m: float,
    network_type: str,
    simplify: bool,
    retain_all: bool,
    truncate_by_edge: bool,
) -> dict[str, Any]:
    lat_o, lon_o = float(origem["lat"]), float(origem["lon"])
    lat_d, lon_d = float(destino["lat"]), float(destino["lon"])
    distancia = distancia_haversine_m(lat_o, lon_o, lat_d, lon_d)
    centro = ((lat_o + lat_d) / 2, (lon_o + lon_d) / 2)

    dist_bbox_m = distancia / 2 + float(margem_m)

    return {
        "center_point": [round(centro[0], 7), round(centro[1], 7)],
        "dist_m": round(dist_bbox_m, 2),
        "network_type": network_type,
        "simplify": bool(simplify),
        "retain_all": bool(retain_all),
        "truncate_by_edge": bool(truncate_by_edge),
        "dist_type": "bbox",
        "cache_schema": 1,
    }


def _caminhos_cache(parametros: dict[str, Any], cache_dir: Path) -> tuple[Path, Path]:
    serializado = json.dumps(parametros, sort_keys=True, separators=(",", ":"))
    identificador = hashlib.sha256(serializado.encode("utf-8")).hexdigest()[:16]
    graph_path = cache_dir / f"osm_graph_{identificador}.graphml"
    metadata_path = cache_dir / f"osm_graph_{identificador}.json"
    return graph_path, metadata_path


def _validar_grafo(G: Any) -> None:
    if G.number_of_nodes() == 0 or G.number_of_edges() == 0:
        raise RuntimeError("O OSMnx retornou um grafo vazio.")
    if not G.is_directed():
        raise RuntimeError("A rede retornada não é direcionada.")
    for u, v, atributos in G.edges(data=True):
        if "length" not in atributos:
            raise ValueError(f"A aresta ({u}, {v}) não possui atributo 'length'.")
        try:
            length = float(atributos["length"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Peso 'length' inválido na aresta ({u}, {v}).") from exc
        if length < 0:
            raise ValueError(f"Peso negativo na aresta ({u}, {v}): {length}.")
        atributos["length"] = length


def obter_grafo_osm_com_cache(
    origem: dict[str, float],
    destino: dict[str, float],
    margem_m: float = 1_500.0,
    network_type: str = "drive",
    simplify: bool = True,
    retain_all: bool = True,
    truncate_by_edge: bool = True,
    force_download: bool = False,
    cache_dir: str | Path | None = None,
) -> tuple[Any, dict[str, Any]]:
    import osmnx as ox

    ensure_project_dirs()
    diretorio = Path(cache_dir) if cache_dir else GRAPH_CACHE_DIR
    diretorio.mkdir(parents=True, exist_ok=True)

    parametros = _parametros_consulta(
        origem,
        destino,
        margem_m,
        network_type,
        simplify,
        retain_all,
        truncate_by_edge,
    )
    graph_path, metadata_path = _caminhos_cache(parametros, diretorio)

    if graph_path.exists() and not force_download:
        print(f"[CACHE] Reutilizando grafo local: {graph_path.name}")
        G_osm = ox.io.load_graphml(filepath=graph_path)
        _validar_grafo(G_osm)
        metadados = {
            "fonte": "cache_local",
            "graphml": str(graph_path),
            "parametros": parametros,
        }
        if metadata_path.exists():
            with metadata_path.open("r", encoding="utf-8") as arquivo:
                metadados_arquivo = json.load(arquivo)
            metadados.update(metadados_arquivo)
            metadados["fonte"] = "cache_local"
        return G_osm, metadados

    print("[OSM] Baixando a malha viária do OpenStreetMap via Overpass...")
    G_osm = ox.graph.graph_from_point(
        center_point=tuple(parametros["center_point"]),
        dist=parametros["dist_m"],
        dist_type=parametros["dist_type"],
        network_type=parametros["network_type"],
        simplify=parametros["simplify"],
        retain_all=parametros["retain_all"],
        truncate_by_edge=parametros["truncate_by_edge"],
    )
    _validar_grafo(G_osm)

    arquivo_temporario = graph_path.with_name(graph_path.stem + ".tmp.graphml")
    ox.io.save_graphml(G_osm, filepath=arquivo_temporario)
    arquivo_temporario.replace(graph_path)

    metadados = {
        "fonte": "download_osm",
        "baixado_em_utc": datetime.now(timezone.utc).isoformat(),
        "graphml": str(graph_path),
        "nos": int(G_osm.number_of_nodes()),
        "arestas": int(G_osm.number_of_edges()),
        "osmnx_version": getattr(ox, "__version__", "desconhecida"),
        "parametros": parametros,
    }
    with metadata_path.open("w", encoding="utf-8") as arquivo:
        json.dump(metadados, arquivo, ensure_ascii=False, indent=2)

    print(
        f"[CACHE] Grafo salvo: {graph_path.name} "
        f"({G_osm.number_of_nodes():,} nós, {G_osm.number_of_edges():,} arestas)."
    )
    return G_osm, metadados


def converter_para_digrafo_ponderado(G_osm: Any, peso: str = "length") -> Any:
    import osmnx as ox

    G = ox.convert.to_digraph(G_osm, weight=peso)
    if not G.is_directed():
        raise RuntimeError("A conversão deveria produzir um grafo direcionado.")
    for u, v, atributos in G.edges(data=True):
        if peso not in atributos:
            raise ValueError(f"A aresta ({u}, {v}) não possui '{peso}'.")
        atributos[peso] = float(atributos[peso])
        if atributos[peso] < 0:
            raise ValueError(f"Peso negativo na aresta ({u}, {v}).")
    return G
