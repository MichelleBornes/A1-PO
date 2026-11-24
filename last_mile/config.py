"""Configurações e caminhos do projeto."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache"
GRAPH_CACHE_DIR = CACHE_DIR / "osm_graphs"
RESULTS_DIR = PROJECT_ROOT / "results"

DEFAULT_JSON = DATA_DIR / "amazon_exemplo.json"
DEFAULT_NETWORK_TYPE = "drive"
DEFAULT_MARGIN_M = 1_500.0
DEFAULT_WEIGHT = "length"

# Parâmetros que alteram o conteúdo/recorte da rede OSM.
DEFAULT_SIMPLIFY = True
DEFAULT_RETAIN_ALL = True
DEFAULT_TRUNCATE_BY_EDGE = True


def ensure_project_dirs() -> None:
    """Cria os diretórios de dados, cache e resultados, se necessário."""
    for directory in (DATA_DIR, GRAPH_CACHE_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
