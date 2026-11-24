from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def carregar_registro_amazon(
    fonte_json: str | Path | dict[str, Any],
    route_id: str | None = None,
    stop_id_destino: str | None = None,
    coordenadas_estacao: tuple[float, float] | None = None,
) -> dict[str, Any]:
    if isinstance(fonte_json, (str, Path)):
        caminho = Path(fonte_json)
        if not caminho.is_file():
            raise FileNotFoundError(f"Arquivo JSON não encontrado: {caminho}")
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    elif isinstance(fonte_json, dict):
        dados = fonte_json
    else:
        raise TypeError("fonte_json deve ser um caminho ou um dicionário Python.")

    if not isinstance(dados, dict) or not dados:
        raise ValueError("O JSON não contém registros de rotas válidos.")

    if route_id is None:
        if len(dados) != 1:
            raise ValueError(
                "O JSON contém várias rotas. Informe route_id para selecionar uma."
            )
        route_id = next(iter(dados))

    if route_id not in dados:
        raise KeyError(f"route_id '{route_id}' não foi encontrado no JSON.")

    rota = dados[route_id]
    if not isinstance(rota, dict) or not isinstance(rota.get("stops"), dict):
        raise ValueError("A rota selecionada não contém o objeto 'stops' esperado.")
    if not rota["stops"]:
        raise ValueError("A rota selecionada não contém paradas.")

    paradas = pd.DataFrame.from_dict(rota["stops"], orient="index")
    paradas.index.name = "stop_id"
    paradas = paradas.reset_index()

    obrigatorias = {"lat", "lng", "type"}
    ausentes = obrigatorias - set(paradas.columns)
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

    tipos = paradas["type"].astype(str).str.strip().str.casefold()
    paradas["type_normalizado"] = tipos
    estacoes = paradas[tipos == "station"]
    entregas = paradas[tipos == "dropoff"]

    if coordenadas_estacao is not None:
        if len(coordenadas_estacao) != 2:
            raise ValueError("coordenadas_estacao deve ser (latitude, longitude).")
        lat_origem, lon_origem = map(float, coordenadas_estacao)
        if not (-90 <= lat_origem <= 90 and -180 <= lon_origem <= 180):
            raise ValueError("As coordenadas externas da estação são inválidas.")
        origem_id = "ORIGEM_EXTERNA"
    elif len(estacoes) == 1:
        estacao = estacoes.iloc[0]
        lat_origem = float(estacao["lat"])
        lon_origem = float(estacao["lng"])
        origem_id = str(estacao["stop_id"])
    elif len(estacoes) > 1:
        raise ValueError(
            "Há mais de uma parada Station. Informe coordenadas_estacao "
            "explicitamente para definir a origem."
        )
    else:
        raise ValueError(
            "Não há parada type='Station'. Informe coordenadas_estacao=(lat, lon). "
            "O campo station_code não contém coordenadas geográficas."
        )

    if entregas.empty:
        raise ValueError("Nenhuma parada type='Dropoff' foi encontrada.")

    if stop_id_destino is None:
        if len(entregas) != 1:
            raise ValueError(
                f"Foram encontradas {len(entregas)} entregas. Informe "
                "stop_id_destino para manter um único destino por execução."
            )
        destino = entregas.iloc[0]
    else:
        selecionada = entregas[
            entregas["stop_id"].astype(str) == str(stop_id_destino)
        ]
        if selecionada.empty:
            raise KeyError(
                f"A parada '{stop_id_destino}' não existe ou não é do tipo Dropoff."
            )
        destino = selecionada.iloc[0]

    return {
        "route_id": str(route_id),
        "station_code": rota.get("station_code"),
        "origem": {
            "stop_id": origem_id,
            "lat": lat_origem,
            "lon": lon_origem,
        },
        "destino": {
            "stop_id": str(destino["stop_id"]),
            "lat": float(destino["lat"]),
            "lon": float(destino["lng"]),
        },
        "paradas": paradas,
        "metadados": {
            "date": rota.get("date_YYYY_MM_DD"),
            "departure_time_utc": rota.get("departure_time_utc"),
            "route_score": rota.get("route_score"),
        },
    }
