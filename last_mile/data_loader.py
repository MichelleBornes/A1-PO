"""Leitura e seleção de rotas do dataset oficial Amazon Last Mile Routing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def carregar_json(fonte_json: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Carrega o objeto JSON raiz do arquivo route_data.json."""
    if isinstance(fonte_json, (str, Path)):
        caminho = Path(fonte_json)
        if not caminho.is_file():
            raise FileNotFoundError(
                f"Arquivo de rotas Amazon não encontrado: {caminho}\n"
                "Baixe-o com: python download_amazon_data.py --split training"
            )
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    elif isinstance(fonte_json, dict):
        dados = fonte_json
    else:
        raise TypeError("fonte_json deve ser um caminho ou um dicionário Python.")

    if not isinstance(dados, dict) or not dados:
        raise ValueError("O JSON não contém um objeto válido de rotas Amazon.")
    return dados


def _dataframe_paradas(rota: dict[str, Any]) -> pd.DataFrame:
    stops = rota.get("stops")
    if not isinstance(stops, dict) or not stops:
        raise ValueError("A rota selecionada não contém o objeto 'stops' esperado.")

    paradas = pd.DataFrame.from_dict(stops, orient="index")
    paradas.index.name = "stop_id"
    paradas = paradas.reset_index()

    obrigatorios = {"lat", "lng", "type"}
    ausentes = obrigatorios - set(paradas.columns)
    if ausentes:
        raise ValueError(f"Campos ausentes nas paradas: {sorted(ausentes)}")

    paradas["lat"] = pd.to_numeric(paradas["lat"], errors="coerce")
    paradas["lng"] = pd.to_numeric(paradas["lng"], errors="coerce")
    if paradas[["lat", "lng"]].isna().any().any():
        raise ValueError("Há coordenadas ausentes ou não numéricas nas paradas.")
    if not paradas["lat"].between(-90, 90).all():
        raise ValueError("Há latitude fora do intervalo [-90, 90].")
    if not paradas["lng"].between(-180, 180).all():
        raise ValueError("Há longitude fora do intervalo [-180, 180].")

    paradas["tipo_normalizado"] = paradas["type"].astype(str).str.strip().str.casefold()
    return paradas


def listar_rotas_amazon(
    fonte_json: str | Path | dict[str, Any],
    limite: int | None = None,
) -> pd.DataFrame:
    """Resume as rotas disponíveis, sem escolher uma origem/destino."""
    dados = carregar_json(fonte_json)
    linhas: list[dict[str, Any]] = []
    for route_id, rota in dados.items():
        if not isinstance(rota, dict):
            continue
        stops = rota.get("stops") or {}
        if not isinstance(stops, dict):
            continue
        tipos = [str(item.get("type", "")).strip().casefold()
                 for item in stops.values() if isinstance(item, dict)]
        linhas.append({
            "route_id": route_id,
            "station_code": rota.get("station_code"),
            "data": rota.get("date_YYYY_MM_DD"),
            "dropoffs": sum(tipo == "dropoff" for tipo in tipos),
            "stations_com_coordenadas": sum(tipo == "station" for tipo in tipos),
            "total_paradas": len(stops),
        })
        if limite is not None and len(linhas) >= limite:
            break
    if not linhas:
        raise ValueError("Nenhuma rota válida foi encontrada no arquivo.")
    return pd.DataFrame(linhas)


def listar_paradas_rota(
    fonte_json: str | Path | dict[str, Any],
    route_id: str,
) -> pd.DataFrame:
    """Lista IDs, tipos e coordenadas das paradas de uma rota."""
    dados = carregar_json(fonte_json)
    if route_id not in dados:
        raise KeyError(f"RouteID '{route_id}' não encontrado.")
    paradas = _dataframe_paradas(dados[route_id])
    colunas = [c for c in ("stop_id", "type", "lat", "lng", "zone_id") if c in paradas]
    return paradas[colunas].sort_values(["type", "stop_id"]).reset_index(drop=True)


def _coordenadas_csv_estacao(
    caminho_csv: str | Path | None,
    station_code: str | None,
) -> tuple[float, float] | None:
    """Consulta um mapa auxiliar station_code -> latitude/longitude."""
    if caminho_csv is None:
        return None
    caminho = Path(caminho_csv)
    if not caminho.is_file():
        return None

    tabela = pd.read_csv(caminho, dtype={"station_code": str})
    requeridas = {"station_code", "latitude", "longitude"}
    ausentes = requeridas - set(tabela.columns)
    if ausentes:
        raise ValueError(
            f"O CSV de estações precisa conter as colunas: {sorted(requeridas)}. "
            f"Ausentes: {sorted(ausentes)}"
        )
    if station_code is None:
        return None

    selecionada = tabela[tabela["station_code"].astype(str).str.strip() == str(station_code).strip()]
    if selecionada.empty:
        return None
    if len(selecionada) > 1:
        raise ValueError(
            f"O CSV possui mais de uma linha para station_code={station_code}. "
            "Mantenha apenas uma coordenada validada por estação."
        )

    latitude = float(selecionada.iloc[0]["latitude"])
    longitude = float(selecionada.iloc[0]["longitude"])
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError(f"Coordenadas inválidas para station_code={station_code}.")
    return latitude, longitude


def carregar_registro_amazon(
    fonte_json: str | Path | dict[str, Any],
    route_id: str | None = None,
    stop_id_destino: str | None = None,
    coordenadas_estacao: tuple[float, float] | None = None,
    station_coordinates_csv: str | Path | None = None,
) -> dict[str, Any]:
    """Extrai uma origem e um único Dropoff de um route_data.json oficial.

    A origem é resolvida nesta ordem:
      1. coordenadas informadas via CLI;
      2. coordenada de uma única parada type='Station' no registro;
      3. arquivo CSV com station_code, latitude e longitude.

    O station_code sozinho é um identificador, não uma coordenada. A função
    nunca assume que o primeiro Dropoff é o centro de distribuição.
    """
    dados = carregar_json(fonte_json)

    if route_id is None:
        if len(dados) != 1:
            raise ValueError(
                "O arquivo possui várias rotas. Informe --route-id ou execute "
                "com --list-routes para consultar os IDs disponíveis."
            )
        route_id = next(iter(dados))
    if route_id not in dados:
        raise KeyError(f"route_id '{route_id}' não foi encontrado no JSON.")

    rota = dados[route_id]
    if not isinstance(rota, dict):
        raise ValueError("O registro da rota não possui formato de objeto JSON.")

    paradas = _dataframe_paradas(rota)
    tipos = paradas["tipo_normalizado"]
    estacoes = paradas[tipos == "station"]
    entregas = paradas[tipos == "dropoff"]
    station_code = rota.get("station_code")

    # Resolver a origem sem atribuir falsamente o primeiro endereço de entrega.
    origem_fonte: str
    origem_id: str
    if coordenadas_estacao is not None:
        if len(coordenadas_estacao) != 2:
            raise ValueError("coordenadas_estacao deve conter (latitude, longitude).")
        lat_origem, lon_origem = map(float, coordenadas_estacao)
        origem_fonte = "coordenadas_informadas_pelo_usuario"
        origem_id = f"STATION_{station_code or 'EXTERNA'}"
    else:
        if len(estacoes) == 1:
            estacao = estacoes.iloc[0]
            lat_origem = float(estacao["lat"])
            lon_origem = float(estacao["lng"])
            origem_fonte = "parada_station_do_route_data"
            origem_id = str(estacao["stop_id"])
        elif len(estacoes) > 1:
            raise ValueError(
                "O registro contém mais de uma parada Station. Informe a origem "
                "explicitamente com --origin-coordinates LAT LON ou no CSV de estações."
            )
        else:
            csv_coords = _coordenadas_csv_estacao(station_coordinates_csv, station_code)
            if csv_coords is not None:
                lat_origem, lon_origem = csv_coords
                origem_fonte = f"arquivo_csv:{Path(station_coordinates_csv).name}"
                origem_id = f"STATION_{station_code or 'EXTERNA'}"
            else:
                raise ValueError(
                    "A rota não contém uma parada type='Station' com coordenadas. "
                    f"station_code={station_code!r} identifica o depósito, mas não informa "
                    "latitude/longitude. Obtenha as coordenadas verificadas dessa estação "
                    "e informe --origin-coordinates LAT LON ou preencha "
                    "data/station_coordinates.csv. Não use o primeiro Dropoff como origem."
                )

    if not (-90 <= lat_origem <= 90 and -180 <= lon_origem <= 180):
        raise ValueError("As coordenadas da estação estão fora dos intervalos válidos.")
    if entregas.empty:
        raise ValueError("Nenhuma parada type='Dropoff' foi encontrada na rota.")

    if stop_id_destino is None:
        if len(entregas) != 1:
            raise ValueError(
                f"A rota possui {len(entregas)} paradas Dropoff. Execute --list-stops "
                "e informe --destination-stop para selecionar apenas um cliente."
            )
        destino = entregas.iloc[0]
    else:
        selecionada = entregas[entregas["stop_id"].astype(str) == str(stop_id_destino)]
        if selecionada.empty:
            raise KeyError(
                f"A parada '{stop_id_destino}' não foi encontrada como Dropoff nessa rota. "
                "Confira os IDs com --list-stops."
            )
        destino = selecionada.iloc[0]

    return {
        "route_id": str(route_id),
        "station_code": station_code,
        "origem": {
            "stop_id": origem_id,
            "lat": float(lat_origem),
            "lon": float(lon_origem),
        },
        "destino": {
            "stop_id": str(destino["stop_id"]),
            "lat": float(destino["lat"]),
            "lon": float(destino["lng"]),
        },
        "origem_fonte": origem_fonte,
        "paradas": paradas,
        "metadados": {
            "date": rota.get("date_YYYY_MM_DD"),
            "departure_time_utc": rota.get("departure_time_utc"),
            "route_score": rota.get("route_score"),
        },
    }
