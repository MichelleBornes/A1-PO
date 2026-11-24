# Otimização de Rotas de Entrega — Dijkstra e A*

Sistema de apoio à decisão para encontrar o caminho mínimo em uma rede viária direcionada e ponderada por distância (`length`, em metros), entre uma origem (estação) e um único destino (cliente).

## 1. Estrutura do projeto

```text
projeto_last_mile/
├── main.py                       # Ponto de entrada / orquestração
├── requirements.txt              # Dependências Python
├── README.md                     # Este guia
├── data/
│   └── amazon_exemplo.json        # Registro sintético para teste
├── last_mile/
│   ├── __init__.py
│   ├── config.py                  # Caminhos e parâmetros padrão
│   ├── data_loader.py             # Leitura do registro Amazon
│   ├── geo.py                     # Haversine e nearest_nodes
│   ├── graph_cache.py             # Download, cache GraphML e conversão
│   ├── algorithms.py              # Dijkstra e A* implementados manualmente
│   ├── evaluation.py              # Tempo, distância e contadores
│   └── visualization.py           # Mapa da rota
├── cache/
│   └── osm_graphs/                # Grafos GraphML locais
├── results/                       # CSV e mapa gerados
└── tests/
    └── test_algoritmos.py         # Testes offline dos algoritmos
```

## 2. Requisitos

- Python 3.10 ou superior (recomendado Python 3.11 ou 3.12; Python 3.14 também é suportado pelas versões atuais das dependências).
- VS Code com a extensão Python da Microsoft.
- Conexão com a internet na primeira execução de uma combinação de coordenadas e parâmetros OSM. As execuções seguintes reutilizam o GraphML local.
- `scikit-learn`, necessário pelo OSMnx para localizar nós em grafos geográficos não projetados (`BallTree`). Ele já está listado no `requirements.txt`.

## 3. Configuração no VS Code

Abra a pasta `projeto_last_mile` no VS Code. No terminal integrado, crie e ative um ambiente virtual.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

No VS Code, selecione o interpretador localizado em `.venv` (`Cmd/Ctrl + Shift + P` → `Python: Select Interpreter`).

> O OSMnx depende de bibliotecas geoespaciais. Se a instalação via `pip` falhar por dependências binárias no seu sistema, a documentação do OSMnx recomenda criar o ambiente pelo Conda/conda-forge. Nesse caso, uma alternativa é `conda create -n last-mile -c conda-forge python=3.11 osmnx networkx pandas matplotlib` e depois `conda activate last-mile`.

As bibliotecas `json` e `time` fazem parte da biblioteca padrão do Python e, portanto, não precisam ser instaladas separadamente.

### Erro `scikit-learn must be installed as an optional dependency`

O OSMnx usa `scikit-learn` para executar `ox.distance.nearest_nodes()` em um grafo não projetado (coordenadas latitude/longitude). Se esse erro aparecer, confirme que o terminal está usando a `.venv` do projeto e execute:

```bash
python -m pip install "scikit-learn>=1.7.2,<2.0"
```

Ou reinstale todas as dependências do projeto:

```bash
python -m pip install -r requirements.txt
```

No Python 3.14, use uma versão atual do `scikit-learn`; a linha 1.7.2 foi a primeira da série 1.7 a oferecer suporte a essa versão do Python.

## 4. Teste offline (não baixa mapa)

Execute primeiro o teste sintético. Ele verifica os algoritmos sem acessar o Overpass ou baixar o OpenStreetMap:

```bash
python main.py --demo
```

Também é possível executar a suíte de testes:

```bash
python -m unittest discover -s tests -v
```

## 5. Execução com OpenStreetMap e cache

O exemplo incluído tem uma parada `Station` e um único `Dropoff`. Para executar:

```bash
python main.py
```

Na primeira execução, o programa:

1. lê origem e destino do JSON;
2. calcula o recorte geográfico em torno dos dois pontos;
3. consulta a rede viária do OpenStreetMap por meio do OSMnx;
4. salva o `MultiDiGraph` como arquivo `.graphml` em `cache/osm_graphs/`;
5. associa as coordenadas aos nós OSM mais próximos;
6. converte a rede para um `DiGraph` direcionado ponderado por `length`;
7. executa Dijkstra e A*;
8. salva a comparação em CSV e o mapa em PNG na pasta `results/`.

Na próxima execução com os mesmos parâmetros, o programa carrega o arquivo GraphML local e **não precisa baixar novamente a rede viária**.

### Atualizar o grafo do cache

O cache é identificado por um hash dos parâmetros de consulta (coordenadas centrais, tamanho do recorte, tipo de rede e opções de construção). Para forçar uma consulta atualizada ao OpenStreetMap:

```bash
python main.py --rebuild-cache
```

Para a mesma chave, o arquivo GraphML existente é substituído pela rede recém-baixada; caches com outras chaves permanecem. Você pode remover manualmente os arquivos em `cache/osm_graphs/` para liberar espaço.

## 6. Usar o dataset real da Amazon

Informe o caminho do `route_data.json`, o `RouteID` e a parada de entrega escolhida. Exemplo:

```bash
python main.py \
  --json "dados/route_data.json" \
  --route-id "ROUTE_ID_REAL" \
  --destination-stop "STOP_ID_REAL"
```

Se o registro não possuir uma parada `Station` com latitude/longitude, forneça as coordenadas da estação separadamente:

```bash
python main.py \
  --json "dados/route_data.json" \
  --route-id "ROUTE_ID_REAL" \
  --destination-stop "STOP_ID_REAL" \
  --origin-coordinates 30.2672 -97.7431
```

Substitua os valores ilustrativos pelas coordenadas numéricas reais (latitude e longitude em graus decimais).

O `station_code` é identificador da estação; ele não substitui coordenadas geográficas. Se o arquivo tiver várias paradas `Dropoff`, `--destination-stop` seleciona exatamente uma, mantendo o escopo de origem única e destino único.

## 7. Argumentos disponíveis

```bash
python main.py --help
```

- `--json`: caminho do arquivo JSON da Amazon.
- `--route-id`: identificador da rota no JSON.
- `--destination-stop`: identificador da parada `Dropoff` escolhida.
- `--origin-coordinates LAT LONG`: coordenadas complementares da estação.
- `--network-type`: `drive` (padrão), `drive_service`, `walk`, `bike`, `all` ou `all_public`.
- `--margin-m`: margem do recorte viário em metros (padrão: 1500).
- `--rebuild-cache`: força novo download.
- `--no-show`: salva o mapa sem abrir uma janela.
- `--demo`: executa somente o teste sintético.

## 8. Arquivos de saída e cache

```text
cache/osm_graphs/
├── osm_graph_<hash>.graphml  # MultiDiGraph original baixado do OSMnx
└── osm_graph_<hash>.json     # metadados e parâmetros da consulta

results/
├── comparacao_algoritmos.csv
└── rota_astar.png
```

O grafo é persistido como **GraphML**, formato indicado pelo OSMnx para salvar e reabrir grafos para análises posteriores. O cache não é uma captura imutável garantida dos dados globais do OSM: ele preserva localmente a rede retornada na data da consulta. Use `--rebuild-cache` quando desejar atualizar os dados.

## 9. Critérios da comparação

| Métrica | Definição |
|---|---|
| Distância total (m) | Soma dos pesos `length` do caminho encontrado |
| Tempo (s) | Tempo de busca medido com `time.perf_counter()`; não inclui download ou plot |
| Vértices explorados | Nós finalizados quando removidos da fila de prioridade com custo confirmado; inclui origem e destino |
| Arestas no caminho | Número de transições entre nós (`len(caminho) - 1`) |

A implementação usa os algoritmos manualmente para tornar explícita a contagem de vértices. A* usa Haversine como heurística. Sua admissibilidade depende de os pesos `length` estarem em metros e não serem menores que a distância geodésica entre os extremos de cada aresta. Dijkstra e A* devem retornar a mesma distância ótima; A* não necessariamente explora menos vértices em todos os grafos.

## 10. Observações metodológicas

- A origem e o destino são associados aos nós OSM mais próximos. Os afastamentos dessa associação são exibidos, mas não são somados à distância do caminho na rede.
- A rede `drive` respeita a direção das vias e não representa automaticamente todos os deslocamentos permitidos a veículos especiais.
- O objetivo é minimizar distância, não tempo de viagem; não há trânsito em tempo real, velocidades, janelas de entrega ou múltiplas paradas.
- Coordenadas anonimizadas/perturbadas da base Amazon podem não apontar para o endereço original exato. Registre essa limitação na análise dos resultados.
