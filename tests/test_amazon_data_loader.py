"""Testes do carregamento e da seleção de rotas do dataset Amazon."""
import json
import tempfile
import unittest
from pathlib import Path

from last_mile.data_loader import (
    carregar_registro_amazon,
    listar_paradas_rota,
    listar_rotas_amazon,
)


def criar_rota(
    incluir_estacao: bool = True,
    dropoffs: tuple[str, ...] = ("AC",),
) -> dict:
    """Cria uma rota sintética com o mesmo formato do route_data.json oficial."""
    stops = {
        "AC": {"lat": 41.831992, "lng": -87.672874, "type": "Dropoff"},
    }
    if incluir_estacao:
        stops["XB"] = {"lat": 41.840375, "lng": -87.683736, "type": "Station"}
    for indice, stop_id in enumerate(dropoffs):
        if stop_id == "AC":
            continue
        stops[stop_id] = {
            "lat": 41.83 + 0.001 * indice,
            "lng": -87.67 + 0.001 * indice,
            "type": "Dropoff",
        }
    return {
        "station_code": "DCH1",
        "date_YYYY_MM_DD": "2018-08-03",
        "departure_time_utc": "2018-08-03T09:00:00Z",
        "route_score": "Good",
        "stops": stops,
    }


class TestAmazonDataLoader(unittest.TestCase):
    def test_origem_vem_da_parada_station(self):
        dados = {"RouteID_TESTE": criar_rota()}
        registro = carregar_registro_amazon(dados)

        self.assertEqual(registro["route_id"], "RouteID_TESTE")
        self.assertEqual(registro["station_code"], "DCH1")
        self.assertEqual(registro["origem_fonte"], "parada_station_do_route_data")
        self.assertEqual(registro["origem"]["stop_id"], "XB")
        self.assertAlmostEqual(registro["origem"]["lat"], 41.840375)
        self.assertAlmostEqual(registro["origem"]["lon"], -87.683736)
        self.assertEqual(registro["destino"]["stop_id"], "AC")
        self.assertEqual(registro["metadados"]["date"], "2018-08-03")

    def test_csv_auxiliar_resolve_estacao_sem_coordenadas(self):
        dados = {"RouteID_TESTE": criar_rota(incluir_estacao=False)}
        with tempfile.TemporaryDirectory() as pasta:
            caminho_csv = Path(pasta) / "station_coordinates.csv"
            caminho_csv.write_text(
                "station_code,latitude,longitude\nDCH1,41.840375,-87.683736\n",
                encoding="utf-8",
            )
            registro = carregar_registro_amazon(
                dados, station_coordinates_csv=caminho_csv
            )

        self.assertEqual(
            registro["origem_fonte"], "arquivo_csv:station_coordinates.csv"
        )
        self.assertAlmostEqual(registro["origem"]["lat"], 41.840375)
        self.assertAlmostEqual(registro["origem"]["lon"], -87.683736)

    def test_coordenadas_explicitas_tem_precedencia(self):
        dados = {"RouteID_TESTE": criar_rota()}
        registro = carregar_registro_amazon(
            dados, coordenadas_estacao=(40.0, -80.0)
        )

        self.assertEqual(registro["origem_fonte"], "coordenadas_informadas_pelo_usuario")
        self.assertAlmostEqual(registro["origem"]["lat"], 40.0)
        self.assertAlmostEqual(registro["origem"]["lon"], -80.0)

    def test_rota_sem_origem_falha(self):
        dados = {"RouteID_TESTE": criar_rota(incluir_estacao=False)}
        with self.assertRaises(ValueError) as contexto:
            carregar_registro_amazon(dados)
        self.assertIn("Station", str(contexto.exception))
        self.assertIn("--origin-coordinates", str(contexto.exception))

    def test_varios_dropoffs_exigem_destino(self):
        dados = {"RouteID_TESTE": criar_rota(dropoffs=("AC", "AD"))}
        with self.assertRaises(ValueError) as contexto:
            carregar_registro_amazon(dados)
        self.assertIn("--destination-stop", str(contexto.exception))

        registro = carregar_registro_amazon(dados, stop_id_destino="AD")
        self.assertEqual(registro["destino"]["stop_id"], "AD")

    def test_mais_de_uma_station_falha(self):
        rota = criar_rota()
        rota["stops"]["XB2"] = {
            "lat": 41.85, "lng": -87.69, "type": "Station",
        }
        with self.assertRaises(ValueError) as contexto:
            carregar_registro_amazon({"RouteID_TESTE": rota})
        self.assertIn("mais de uma parada Station", str(contexto.exception))

    def test_arquivo_com_varias_rotas_exige_route_id(self):
        dados = {
            "RouteID_A": criar_rota(),
            "RouteID_B": criar_rota(),
        }
        with self.assertRaises(ValueError) as contexto:
            carregar_registro_amazon(dados)
        self.assertIn("--route-id", str(contexto.exception))

    def test_route_id_inexistente_falha(self):
        with self.assertRaises(KeyError):
            carregar_registro_amazon({"RouteID_TESTE": criar_rota()}, route_id="OUTRA")

    def test_leitura_de_arquivo_json(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "route_data.json"
            caminho.write_text(
                json.dumps({"RouteID_TESTE": criar_rota()}), encoding="utf-8"
            )
            registro = carregar_registro_amazon(caminho, route_id="RouteID_TESTE")
        self.assertEqual(registro["destino"]["stop_id"], "AC")

    def test_listar_rotas_e_paradas(self):
        dados = {"RouteID_TESTE": criar_rota()}
        rotas = listar_rotas_amazon(dados)
        self.assertEqual(rotas.loc[0, "route_id"], "RouteID_TESTE")
        self.assertEqual(int(rotas.loc[0, "dropoffs"]), 1)
        self.assertEqual(int(rotas.loc[0, "stations_com_coordenadas"]), 1)
        self.assertEqual(int(rotas.loc[0, "total_paradas"]), 2)

        paradas = listar_paradas_rota(dados, "RouteID_TESTE")
        self.assertEqual(list(paradas["stop_id"]), ["AC", "XB"])
        self.assertEqual(
            list(paradas["type"]), ["Dropoff", "Station"]
        )
        with self.assertRaises(KeyError):
            listar_paradas_rota(dados, "OUTRA")


if __name__ == "__main__":
    unittest.main()
