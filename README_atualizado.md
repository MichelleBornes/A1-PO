# Otimização de Rotas — Amazon Last Mile + OpenStreetMap + Dijkstra/A*

Sistema de apoio à decisão para encontrar o caminho de menor distância em uma rede viária direcionada e ponderada pelo atributo `length` (metros), entre uma estação de distribuição e uma única parada `Dropoff`.

> **Esta versão utiliza o formato do dataset oficial Amazon Last Mile Routing Research Challenge.** O JSON sintético foi separado em `data/examples/` e deve ser utilizado apenas em testes de leitura ou demonstrações. Ele não é a fonte dos resultados experimentais apresentados como dados da Amazon.

## 1. Objetivo e escopo

O projeto compara os algoritmos Dijkstra e A* para resolver um problema de caminho mínimo em uma malha viária real extraída do OpenStreetMap.

A cada execução, o sistema considera:

- uma origem: estação de distribuição;
- um destino: uma única parada `Dropoff`;
- um grafo direcionado, em que os vértices representam nós da rede viária e as arestas representam segmentos de ruas;
- o comprimento `length` das arestas, em metros, como custo a minimizar.

O projeto **não** resolve múltiplas entregas, roteirização de frotas, trânsito em tempo real ou janelas de entrega. A sequência completa de paradas do motorista na base Amazon não é reproduzida: o sistema resolve um subproblema entre uma estação e um único cliente.

## 2. Dataset Amazon: formato e cuidados com a origem

O Amazon Last Mile Routing Research Challenge reúne 9.184 rotas históricas de 2018. O arquivo `route_data.json` contém informações como `station_code`, data, horário de saída e uma lista `stops`. Cada parada pode conter `lat`, `lng`, `type` e `zone_id`.

### Como o projeto identifica a origem

`station_code` é um identificador textual da estação; **não é uma latitude/longitude**. O programa resolve a origem nesta ordem:

1. utiliza a única parada `Station` com coordenadas presente no registro, quando existir;
2. caso não exista, consulta `data/station_coordinates.csv`;
3. se ainda não encontrar, exige coordenadas verificadas por meio de `--origin-coordinates LATITUDE LONGITUDE`.

O sistema não utiliza o primeiro cliente como origem e não deduz coordenadas a partir de `station_code`. Quando a origem é complementada externamente, a fonte das coordenadas deve ser registrada para que o experimento seja reproduzível.

As coordenadas de paradas Amazon são anonimizadas/perturbadas. Por isso, a associação ao nó OSM mais próximo é aproximada e não necessariamente corresponde ao endereço original exato.

## 3. Estrutura do projeto

```text
projeto_last_mile/
├── main.py                           # Orquestração do experimento
├── download_amazon_data.py           # Download do JSON de rotas no AWS Open Data
├── requirements.txt                  # Dependências Python
├── README.md
├── .gitignore
├── data/
│   ├── amazon/                        # route_data.json oficial (baixado localmente)
│   ├── examples/
│   │   └── amazon_exemplo_sintetico.json  # somente teste/demonstração
│   └── station_coordinates.csv        # station_code -> coordenadas verificadas (opcional)
├── last_mile/
│   ├── __init__.py
│   ├── config.py                      # caminhos e parâmetros padrão
│   ├── data_loader.py                 # leitura de RouteID, Station e Dropoff
│   ├── geo.py                         # Haversine e associação nearest_nodes
│   ├── graph_cache.py                 # extração OSM, cache GraphML e conversão do grafo
│   ├── algorithms.py                  # implementações manuais de Dijkstra e A*
│   ├── evaluation.py                  # medições repetidas e comparação
│   └── visualization.py               # mapas das rotas
├── cache/
│   └── osm_graphs/                    # grafos GraphML e metadados do cache
├── results/                           # CSV, JSON e mapas gerados
└── tests/
    ├── test_algoritmos.py
    └── test_amazon_data_loader.py
```

Os diretórios `data/amazon/`, `cache/osm_graphs/` e `results/` são utilizados localmente. O dataset completo e os grafos baixados não devem ser enviados ao Git.

## 4. Instalação no macOS e VS Code

Abra a pasta do projeto no VS Code e execute os comandos no terminal integrado.

### 4.1 Criar e ativar o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

No VS Code, selecione o interpretador da `.venv` com `Cmd + Shift + P` → `Python: Select Interpreter`.

### 4.2 Instalar a AWS CLI

A AWS CLI é utilizada para copiar o arquivo público no S3. No macOS com Homebrew:

```bash
brew install awscli
aws --version
```

O bucket é público; o download do script utiliza `--no-sign-request` e não exige credenciais AWS.

## 5. Baixar os dados oficiais da Amazon

O dataset completo contém outros arquivos de dados além das coordenadas das rotas. Para este projeto, o primeiro experimento precisa do `route_data.json`. O script `download_amazon_data.py` baixa somente esse objeto do bucket público.

Para baixar o conjunto de treinamento:

```bash
python download_amazon_data.py --split training
```

O arquivo será salvo em:

```text
data/amazon/route_data.json
```

Para sobrescrever um arquivo que já existe:

```bash
python download_amazon_data.py --split training --force
```

Também é possível baixar o split de avaliação:

```bash
python download_amazon_data.py --split evaluation
```

O caminho padrão de execução é `data/amazon/route_data.json`. Para utilizar outro arquivo, informe `--json CAMINHO` nos comandos de `main.py`.

## 6. Listar rotas e consultar as paradas

Depois do download, liste as rotas disponíveis:

```bash
python main.py --list-routes
```

Por padrão, são exibidas até 30 rotas. Para listar todas:

```bash
python main.py --list-routes --limit 0
```

A listagem apresenta o identificador `route_id`, `station_code`, data e quantidades de paradas `Dropoff` e `Station` com coordenadas.

Copie o valor completo da coluna `route_id` (não confunda com `station_code`) e consulte as paradas:

```bash
python main.py --route-id "RouteID_ESCOLHIDO" --list-stops
```

Escolha um único `stop_id` cujo tipo seja `Dropoff`. O escopo do projeto é uma origem e um destino por execução.

## 7. Rota selecionada para o primeiro experimento

Na consulta realizada ao dataset oficial, foi encontrada a seguinte rota:

| Campo | Valor |
|---|---|
| `route_id` | `RouteID_0074e307-23c1-4b15-afa2-e58b45e4403c` |
| `station_code` | `DLA7` |
| Origem (`Station`) | `XB` |
| Latitude da origem | `41.840375` |
| Longitude da origem | `-87.683736` |
| Destino (`Dropoff`) | `AC` |
| Latitude do destino | `41.831992` |
| Longitude do destino | `-87.672874` |

A listagem da rota mostrou uma parada `Station` com coordenadas (`XB`) e várias paradas `Dropoff`. Portanto, para esta rota, o programa pode obter a origem diretamente do JSON. **Não é necessário preencher `station_coordinates.csv` nem informar `--origin-coordinates` para executar este exemplo**, desde que o `route_data.json` local seja o mesmo dataset e registro consultados.

Para consultar novamente as paradas desta rota:

```bash
python main.py \
  --route-id "RouteID_0074e307-23c1-4b15-afa2-e58b45e4403c" \
  --list-stops
```

## 8. Executar Dijkstra e A* com a rota selecionada

Para executar o experimento com a origem `XB` e o destino `AC`:

```bash
python main.py \
  --route-id "RouteID_0074e307-23c1-4b15-afa2-e58b45e4403c" \
  --destination-stop "AC" \
  --repetitions 30
```

O parâmetro `--repetitions 30` solicita 30 medições cronometradas de cada algoritmo, além de uma execução de aquecimento que não entra nas medições. Se omitido, o padrão é 10 repetições.

Para utilizar outro `route_data.json` explicitamente:

```bash
python main.py \
  --json "data/amazon/route_data.json" \
  --route-id "RouteID_ESCOLHIDO" \
  --destination-stop "ID_DO_DROPOFF"
```

Se a rota não possuir parada `Station` com coordenadas nem correspondência no CSV, obtenha coordenadas da estação por uma fonte verificável e execute:

```bash
python main.py \
  --route-id "RouteID_ESCOLHIDO" \
  --destination-stop "ID_DO_DROPOFF" \
  --origin-coordinates LATITUDE LONGITUDE
```

Substitua `LATITUDE` e `LONGITUDE` pelas coordenadas verificadas da estação correspondente. Não utilize as coordenadas de um `Dropoff` como origem.

Para salvar os mapas sem abrir janelas do Matplotlib, adicione `--no-show` ao comando.

## 9. Como o programa executa o experimento

Ao iniciar, `main.py` realiza as seguintes etapas:

1. carrega o registro escolhido no dataset Amazon;
2. resolve as coordenadas da estação e do `Dropoff` selecionado;
3. extrai a rede viária `drive` do OpenStreetMap, ou reutiliza o cache local;
4. associa a origem e o destino aos nós OSM mais próximos com `ox.distance.nearest_nodes`;
5. converte a rede para um grafo direcionado ponderado por `length`;
6. executa Dijkstra e A* no mesmo grafo e entre os mesmos nós;
7. mede os tempos de busca com `time.perf_counter()`;
8. apresenta distância, tempo mediano, tempo médio, vértices explorados e arestas do caminho;
9. salva os mapas e os metadados da execução.

A medição de tempo considera somente a busca realizada pelo algoritmo. Não inclui a leitura do JSON, download do OSM, associação geográfica, conversão do grafo ou geração dos mapas.

## 10. Cache local da malha viária OSM

O grafo original `MultiDiGraph` é salvo em `cache/osm_graphs/*.graphml`, e os metadados da consulta são armazenados em arquivos JSON correspondentes. Quando a execução seguinte utiliza a mesma combinação de coordenadas e parâmetros, o grafo é carregado localmente.

Assim, não é necessário consultar novamente o OpenStreetMap para a mesma região e configuração.

Para forçar uma nova consulta ao OSM:

```bash
python main.py \
  --route-id "RouteID_ESCOLHIDO" \
  --destination-stop "ID_DO_DROPOFF" \
  --rebuild-cache
```

O cache é específico da área e dos parâmetros da consulta. Uma rota em outra região pode gerar outro arquivo GraphML.

## 11. Arquivos gerados

Após uma execução bem-sucedida, a pasta `results/` conterá:

```text
results/
├── comparacao_algoritmos_amazon_osm.csv
├── execucao_amazon_osm.json
├── rota_dijkstra.png
└── rota_astar.png
```

O CSV contém a comparação das métricas. O JSON registra o `RouteID`, `station_code`, origem, fonte das coordenadas, destino, associação aos nós OSM e métricas. Os arquivos PNG mostram as rotas calculadas por cada algoritmo.

## 12. Testes e demonstração sintética

Os testes automatizados não precisam consultar a internet e não representam resultados experimentais da Amazon. Execute:

```bash
python -m unittest discover -s tests -v
```

Também existe uma demonstração isolada em um pequeno grafo sintético:

```bash
python main.py --demo
```

Use `--demo` apenas para verificar a lógica dos algoritmos. Não apresente os resultados desse modo como resultados obtidos com o dataset Amazon.

## 13. Critérios de avaliação e interpretação

- Dijkstra e A* recebem o mesmo grafo direcionado, a mesma origem e o mesmo destino.
- Os custos das arestas são os comprimentos OSM `length`, em metros. O objetivo é minimizar distância, não tempo de viagem.
- A heurística do A* é a distância Haversine em metros. Sua admissibilidade depende de os pesos `length` não serem inferiores à distância geodésica entre os extremos das arestas.
- O tempo de busca é medido com `time.perf_counter()`. O relatório apresenta mediana e média das repetições para reduzir o impacto de variações ocasionais em medições muito pequenas.
- O contador de vértices explorados considera os nós retirados da fila de prioridade e finalizados, incluindo origem e destino.
- A* pode explorar menos vértices que Dijkstra, mas isso não é garantido em todos os grafos.
- Coordenadas Amazon anonimizadas/perturbadas tornam aproximada a associação com a malha viária OSM. Essa limitação deve ser mencionada na apresentação.
- O projeto resolve apenas um trecho origem-destino. Não reproduz a sequência de todas as entregas de uma rota histórica Amazon.

## 14. Git: o que deve ser versionado

Versione o código-fonte, testes, documentação e arquivos de configuração. Não versione o ambiente virtual, o JSON completo do dataset, grafos OSM em cache ou resultados volumosos gerados localmente.

O `.gitignore` do projeto já deve excluir, entre outros:

```gitignore
.venv/
__pycache__/
*.py[cod]
.DS_Store
cache/osm_graphs/*
!cache/osm_graphs/.gitkeep
results/*
!results/.gitkeep
data/amazon/*.json
```

Antes de realizar o commit, confira:

```bash
git status
python -m unittest discover -s tests -v
```

## 15. Referências e licença dos dados

- Amazon Open Data Registry — 2021 Amazon Last Mile Routing Research Challenge Dataset: <https://registry.opendata.aws/amazon-last-mile-challenges/>
- MIT-CAVE — documentação do formato dos arquivos: <https://github.com/MIT-CAVE/rc-cli/blob/main/templates/data_structures.md>
- Merchán, D.; Arora, J.; Pachon, J.; Konduri, K.; Winkenbach, M.; Parks, S.; Noszek, J. (2022). *2021 Amazon Last Mile Routing Research Challenge: Data Set*. Transportation Science. <https://doi.org/10.1287/trsc.2022.1173>
- OSMnx — documentação: <https://osmnx.readthedocs.io/>

A base Amazon é disponibilizada sob licença Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0). Confira as condições da licença antes de redistribuir os dados ou utilizá-los para fins comerciais.
