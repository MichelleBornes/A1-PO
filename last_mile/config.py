"""Configurações e caminhos do projeto."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AMAZON_DATA_DIR = DATA_DIR / "amazon"
EXAMPLES_DIR = DATA_DIR / "examples"
CACHE_DIR = PROJECT_ROOT / "cache"
GRAPH_CACHE_DIR = CACHE_DIR / "osm_graphs"
RESULTS_DIR = PROJECT_ROOT / "results"

# O projeto passa a apontar para a base oficial. O arquivo é baixado pelo script
# download_amazon_data.py; não incluímos a base no ZIP porque ela é grande.
DEFAULT_JSON = AMAZON_DATA_DIR / "route_data.json"
DEFAULT_STATION_COORDINATES_CSV = DATA_DIR / "station_coordinates.csv"
DEFAULT_NETWORK_TYPE = "drive"
DEFAULT_MARGIN_M = 1_500.0
DEFAULT_WEIGHT = "length"
DEFAULT_REPETITIONS = 10

# Parâmetros que alteram o conteúdo/recorte da rede OSM.
DEFAULT_SIMPLIFY = True
DEFAULT_RETAIN_ALL = True
DEFAULT_TRUNCATE_BY_EDGE = True


def ensure_project_dirs() -> None:
    """Cria os diretórios de dados, cache e resultados, se necessário."""
    for directory in (AMAZON_DATA_DIR, EXAMPLES_DIR, GRAPH_CACHE_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)