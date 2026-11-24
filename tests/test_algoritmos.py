"""Testes automatizados básicos dos algoritmos (stdlib unittest)."""
import unittest

import networkx as nx

from last_mile.algorithms import a_estrela_manual, dijkstra_manual


def criar_grafo_teste() -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_node("S", x=0.000, y=0.000)
    G.add_node("A", x=0.001, y=0.000)
    G.add_node("B", x=0.000, y=0.001)
    G.add_node("T", x=0.002, y=0.000)
    G.add_edge("S", "A", length=120.0)
    G.add_edge("A", "T", length=120.0)
    G.add_edge("S", "B", length=130.0)
    G.add_edge("B", "T", length=300.0)
    return G


class TestAlgoritmos(unittest.TestCase):
    def test_mesma_distancia_otima(self):
        G = criar_grafo_teste()
        d = dijkstra_manual(G, "S", "T")
        a = a_estrela_manual(G, "S", "T")
        self.assertAlmostEqual(d["distancia_m"], 240.0)
        self.assertAlmostEqual(a["distancia_m"], d["distancia_m"])
        self.assertEqual(d["caminho"], ["S", "A", "T"])
        self.assertEqual(a["caminho"], ["S", "A", "T"])

    def test_trace_registra_extracoes_e_relaxamentos(self):
        G = criar_grafo_teste()

        eventos_d: list[dict] = []
        d = dijkstra_manual(G, "S", "T", registrar=eventos_d.append)
        self.assertAlmostEqual(d["distancia_m"], 240.0)
        extracoes = [e["no"] for e in eventos_d if e["evento"] == "extrai"]
        self.assertEqual(extracoes, ["S", "A", "B", "T"])
        relaxamentos = [e for e in eventos_d if e["evento"] == "relaxa"]
        self.assertTrue(any(
            e["de"] == "S" and e["para"] == "A" and e["depois"] == 120.0
            for e in relaxamentos
        ))

        eventos_a: list[dict] = []
        a = a_estrela_manual(G, "S", "T", registrar=eventos_a.append)
        self.assertAlmostEqual(a["distancia_m"], 240.0)
        extracoes_a = [e["no"] for e in eventos_a if e["evento"] == "extrai"]
        self.assertEqual(extracoes_a, ["S", "A", "T"])
        self.assertIn("f", eventos_a[0])
        relaxamentos_a = [e for e in eventos_a if e["evento"] == "relaxa"]
        self.assertTrue(any(
            e["de"] == "A" and e["para"] == "T" and e["f"] == 240.0
            for e in relaxamentos_a
        ))

    def test_grafo_direcionado_respeita_sentido(self):
        G = nx.DiGraph()
        G.add_node("S", x=0.0, y=0.0)
        G.add_node("T", x=0.001, y=0.0)
        G.add_edge("T", "S", length=100.0)
        with self.assertRaises(nx.NetworkXNoPath):
            dijkstra_manual(G, "S", "T")

    def test_peso_negativo_rejeitado(self):
        G = nx.DiGraph()
        G.add_edge("S", "T", length=-1.0)
        with self.assertRaises(ValueError):
            dijkstra_manual(G, "S", "T")


if __name__ == "__main__":
    unittest.main()
