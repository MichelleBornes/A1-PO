# Otimização de Rotas — Amazon Last Mile + OpenStreetMap + Dijkstra/A*

Sistema de apoio à decisão para encontrar o caminho de menor distância em uma rede viária direcionada e ponderada pelo atributo `length` (metros), entre uma estação de distribuição e uma única parada `Dropoff`.

> **Esta versão utiliza o formato do dataset oficial Amazon Last Mile Routing Research Challenge.** O JSON sintético `data/amazon_exemplo.json` deve ser utilizado apenas em testes de leitura ou demonstrações. Ele não é a fonte dos resultados experimentais apresentados como dados da Amazon.

## 1. Objetivo e escopo

O projeto compara os algoritmos Dijkstra e A* para resolver um problema de caminho mínimo em uma malha viária real extraída do OpenStreetMap.

A cada execução, o sistema considera:

- uma origem: estação de distribuição;
- um destino: uma única parada `Dropoff`;
- um grafo direcionado, em que os vértices representam nós da rede viária e as arestas representam segmentos de ruas;
- o comprimento `length` das arestas, em metros, como custo a minimizar.

O projeto **não** resolve múltiplas entregas, roteirização de frotas, trânsito em tempo real ou janelas de entrega. A sequência completa de paradas do motorista na base Amazon não é reproduzida: o sistema resolve um subproblema entre uma estação e um único cliente.

### 1.1 Modelo formal

O problema resolvido é o **caminho mínimo em um grafo direcionado e ponderado**. A formulação de programação linear inteira abaixo é equivalente ao problema; o código o resolve de forma exata com Dijkstra e A*.

- **Conjuntos:** $V$ é o conjunto de nós da malha viária; $A \subseteq V \times V$ é o conjunto de segmentos de rua orientados; $s \in V$ é a origem (estação) e $t \in V$ é o destino (cliente).
- **Parâmetros:** para cada arco $(i,j) \in A$, o peso $w_{ij} = \text{length}_{ij} \ge 0$, em metros, é o comprimento do segmento de rua.
- **Variáveis de decisão:** $x_{ij} \in \{0,1\}$, em que $x_{ij}=1$ se o arco $(i,j)$ pertence ao caminho escolhido e $x_{ij}=0$ caso contrário.
- **Função objetivo:** minimizar a distância total percorrida:

$$
\min Z = \sum_{(i,j)\in A} w_{ij}\,x_{ij}
$$

- **Restrições de conservação de fluxo:** uma unidade de fluxo sai de $s$, chega a $t$ e não é criada nem consumida nos demais nós:

$$
\sum_{j:(i,j)\in A} x_{ij} \;-\; \sum_{j:(j,i)\in A} x_{ji} =
\begin{cases}
1, & i = s,\\
-1, & i = t,\\
0, & i \in V \setminus \{s,t\}.
\end{cases}
$$

- **Domínio:** $x_{ij} \in \{0,1\}$ para todo $(i,j)\in A$.

No código, $V$ e $A$ vêm do grafo direcionado extraído do OpenStreetMap, e $w_{ij}$ é o atributo `length` de cada aresta. A origem $s$ e o destino $t$ são os nós OSM mais próximos das coordenadas da estação e do cliente (`last_mile/geo.py` e `last_mile/graph_cache.py`). Como todos os pesos são não negativos e a rede é direcionada, Dijkstra e A* resolvem essa formulação de forma exata.

### 1.2 Forma de cálculo dos algoritmos

**Dijkstra.** Mantém uma fila de prioridade com os vértices candidatos e a melhor distância conhecida `d[v]` para cada um. Inicialmente, `d[s] = 0` e `d[v] = ∞` para os demais. Em cada passo, retira da fila o vértice de menor `d`, finaliza-o e tenta melhorar os vizinhos (*relaxamento*): se `d[u] + w_uv < d[v]`, atualiza `d[v]`, guarda o predecessor e insere `v` na fila. O algoritmo termina quando o destino é retirado da fila (ou quando a fila esvazia). Complexidade: `O((|V| + |A|) log |V|)` com heap binário.

**A*.** É o Dijkstra guiado por uma estimativa `h(v)` do custo restante até o destino. A fila é ordenada por `f(v) = g(v) + h(v)`, em que `g(v)` é o custo real já percorrido. A implementação usa `h(v)` = distância Haversine em linha reta entre `v` e `t`, que nunca supera o custo real em metros quando `length` não é menor que a distância Haversine entre os nós extremos da aresta. Com heurística admissível, o primeiro destino retirado da fila tem custo ótimo, como no Dijkstra; na prática, A* finaliza menos vértices porque descarta primeiro os ramos que se afastam do destino.

O código conta um vértice como *explorado* quando ele é retirado da fila com o menor custo confirmado, incluindo origem e destino. O parâmetro `--trace N` imprime os primeiros `N` eventos de extração e relaxamento de cada algoritmo (exemplo na seção 9.1).

## 2. Dataset Amazon: formato e cuidados com a origem

O Amazon Last Mile Routing Research Challenge reúne 9.184 rotas históricas de 2018. O arquivo `route_data.json` contém informações como `station_code`, data, horário de saída e uma lista `stops`. Cada parada pode conter `lat`, `lng`, `type` e `zone_id`. O split de treinamento baixado por este projeto contém 6.112 rotas.

### Como o projeto identifica a origem

`station_code` é um identificador textual da estação; **não é uma latitude/longitude**. O programa resolve a origem nesta ordem:

1. utiliza as coordenadas informadas por `--origin-coordinates LATITUDE LONGITUDE`, quando fornecidas;
2. caso contrário, utiliza a única parada `Station` com coordenadas presente no registro;
3. se não houver `Station` com coordenadas, consulta `data/station_coordinates.csv`;
4. se nenhuma fonte fornecer coordenadas, encerra com erro pedindo `--origin-coordinates`.

O sistema não utiliza o primeiro cliente como origem e não deduz coordenadas a partir de `station_code`. Quando a origem é complementada externamente, a fonte das coordenadas deve ser registrada para que o experimento seja reproduzível.

As coordenadas de paradas Amazon são anonimizadas/perturbadas. Por isso, a associação ao nó OSM mais próximo é aproximada e não necessariamente corresponde ao endereço original exato.

## 3. Estrutura do projeto

```text
A1-PO/
├── main.py                           # Orquestração do experimento e CLI
├── download_amazon_data.py           # Download do JSON de rotas no AWS Open Data
├── requirements.txt                  # Dependências Python
├── README.md                         # Documentação técnica e resultados
├── .gitignore
├── data/
│   ├── amazon/
│   │   └── route_data.json            # dataset oficial (split de treinamento)
│   ├── amazon_exemplo.json            # rota sintética, somente teste/demonstração
│   └── station_coordinates.csv        # station_code -> coordenadas verificadas (opcional)
├── last_mile/
│   ├── __init__.py
│   ├── config.py                      # caminhos e parâmetros padrão
│   ├── data_loader.py                 # leitura de RouteID, Station e Dropoff
│   ├── geo.py                         # Haversine e associação nearest_nodes
│   ├── graph_cache.py                 # extração OSM, cache GraphML e conversão do grafo
│   ├── algorithms.py                  # implementações manuais de Dijkstra e A* (+ trace)
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

## 4. Instalação (macOS ou Windows) e VS Code

Abra a pasta do projeto no VS Code e execute os comandos no terminal integrado.

### 4.1 Criar e ativar o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

No Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente virtual, execute uma vez na sessão atual: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

No VS Code, selecione o interpretador da `.venv` com `Cmd + Shift + P` (macOS) ou `Ctrl + Shift + P` (Windows) → `Python: Select Interpreter`.

### 4.2 Instalar a AWS CLI

A AWS CLI é utilizada para copiar o arquivo público no S3. No macOS com Homebrew:

```bash
brew install awscli
aws --version
```

O bucket é público; o download do script utiliza `--no-sign-request` e não exige credenciais AWS.

No Windows, instale a AWS CLI com o winget (ou, se preferir, dentro da `.venv`, com `python -m pip install awscli`):

```powershell
winget install Amazon.AWSCLI
aws --version
```

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
| `station_code` | `DCH1` |
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

Para sobrescrever a origem ou quando a rota não possuir parada `Station` com coordenadas nem correspondência no CSV, obtenha coordenadas da estação por uma fonte verificável e execute:

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

### 9.1 Demonstração passo a passo do cálculo

O grafo sintético de `python main.py --demo` tem quatro vértices e serve para conferir as contas:

| Arco | Peso (m) |
|---|---:|
| S → A | 120,00 |
| A → T | 120,00 |
| S → B | 130,00 |
| B → T | 300,00 |

**Dijkstra.** Inicialização: `d[S] = 0`, `d[A] = d[B] = d[T] = ∞`. A fila começa com `(0, S)`.

| Passo | Extraído | `d` (m) | Relaxamentos | Fila após o passo |
|---|---|---|---|---|
| 1 | S | 0,00 | S→A: ∞ → 120,00; S→B: ∞ → 130,00 | (120, A), (130, B) |
| 2 | A | 120,00 | A→T: ∞ → 240,00 | (130, B), (240, T) |
| 3 | B | 130,00 | B→T: 130 + 300 = 430,00 > 240,00 (não atualiza) | (240, T) |
| 4 | T | 240,00 | Destino finalizado | vazia |

Caminho ótimo: `S → A → T`, com 240,00 m. Foram finalizados 4 vértices.

**A\*.** A heurística é `h(v)` = Haversine de `v` até `T`: `h(S) = 191,83 m`, `h(A) = 95,92 m`, `h(B) = 221,73 m` e `h(T) = 0`. A fila é ordenada por `f = g + h`.

| Passo | Extraído | `g` (m) | `h` (m) | `f` (m) | Relaxamentos | Fila após o passo |
|---|---|---|---|---|---|---|
| 1 | S | 0,00 | 191,83 | 191,83 | S→A: g=120,00, f=215,92; S→B: g=130,00, f=351,73 | (215,92 A), (351,73 B) |
| 2 | A | 120,00 | 95,92 | 215,92 | A→T: g=240,00, h=0, f=240,00 | (240,00 T), (351,73 B) |
| 3 | T | 240,00 | 0,00 | 240,00 | Destino finalizado | vazia |

O destino é retirado antes de `B` porque `f(T) = 240,00 < f(B) = 351,73`. Caminho: `S → A → T`, 240,00 m; foram finalizados 3 vértices (contra 4 no Dijkstra).

Na execução real, use `--trace` para ver as mesmas informações com os nós OSM. Exemplo com a rota da seção 7:

```bash
python main.py \
  --route-id "RouteID_0074e307-23c1-4b15-afa2-e58b45e4403c" \
  --destination-stop "AC" \
  --trace 7 --no-show
```

Trecho da saída (808 eventos no Dijkstra e 114 no A*; as 7 primeiras linhas de cada algoritmo):

```text
=== PRIMEIROS PASSOS — Dijkstra (808 eventos registrados) ===
  extrai 357536480 | g=0.00 m | fila=0
  relaxa 357536480->261160969 | peso=391.74 m | infinito -> 391.74 m
  relaxa 357536480->261120575 | peso=236.44 m | infinito -> 236.44 m
  relaxa 357536480->261295769 | peso=247.37 m | infinito -> 247.37 m
  extrai 261120575 | g=236.44 m | fila=2
  relaxa 261120575->261120580 | peso=359.89 m | infinito -> 596.34 m
  relaxa 261120575->12245099254 | peso=70.77 m | infinito -> 307.21 m
  ... (801 eventos omitidos)

=== PRIMEIROS PASSOS — A* (114 eventos registrados) ===
  extrai 357536480 | g=0.00 m | f=1,430.17 m | fila=0
  relaxa 357536480->261160969 | peso=391.74 m | infinito -> 391.74 m
  relaxa 357536480->261120575 | peso=236.44 m | infinito -> 236.44 m
  relaxa 357536480->261295769 | peso=247.37 m | infinito -> 247.37 m
  extrai 261120575 | g=236.44 m | f=1,509.62 m | fila=2
  relaxa 261120575->261120580 | peso=359.89 m | infinito -> 596.34 m
  relaxa 261120575->12245099254 | peso=70.77 m | infinito -> 307.21 m
  ... (107 eventos omitidos)
```

Cada `extrai` mostra o vértice finalizado e o custo acumulado (`g`; no A*, também `f`); cada `relaxa` mostra o arco, o peso e a atualização do custo (`infinito` antes do primeiro caminho).

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

### 11.1 Resultados de referência

Execução de referência com a rota da seção 7, grafo OSM em cache (914 nós e 2.395 arestas direcionadas) e 10 repetições:

```bash
python main.py \
  --route-id "RouteID_0074e307-23c1-4b15-afa2-e58b45e4403c" \
  --destination-stop "AC" \
  --repetitions 10 --no-show
```

| Algoritmo | Distância (m) | Tempo mediano (ms) | Tempo médio (ms) | Vértices finalizados | Arestas no caminho |
|---|---:|---:|---:|---:|---:|
| Dijkstra | 2.079,418 | 1,103 | 1,104 | 344 | 17 |
| A* | 2.079,418 | 0,283 | 0,289 | 44 | 17 |

As duas buscas encontram o mesmo caminho ótimo e o mesmo custo. Nessa execução, A* finalizou 87,2% menos vértices e foi cerca de 3,89 vezes mais rápido na medição mediana (74,3% menos tempo). Os tempos absolutos variam entre execuções e máquinas: os valores da tabela são de uma execução de referência e o CSV em `results/` guarda os valores exatos da execução mais recente (podem diferir em frações de milissegundo).

Associação das coordenadas (as coordenadas Amazon são perturbadas):

| Ponto | Nó OSM | Afastamento até o nó |
|---|---|---:|
| Origem (XB) | 357536480 | 158,54 m |
| Destino (AC) | 261228662 | 30,16 m |

Os mapas `rota_dijkstra.png` e `rota_astar.png` mostram a malha viária, a rota em destaque, a origem, o destino e as coordenadas originais.

## 12. Análise de impacto e decisão

O resultado principal é uma rota de **2.079,42 m** entre a estação e o cliente. Para interpretar esse número, a tabela compara com duas referências geométricas calculadas com as mesmas coordenadas (a rota não é uma delas):

| Referência | Distância | Razão rota/referência |
|---|---:|---:|
| Linha reta (Haversine) | 1.295,64 m | 1,605 |
| Manhattan (soma Haversine dos eixos) | 1.831,97 m | 1,135 |

A rota é 60,5% mais longa que a linha reta e 13,5% mais longa que a estimativa Manhattan — coerente com uma malha viária ortogonal e com a obrigação de seguir ruas de mão única.

### Ganho computacional

- O custo ótimo é idêntico: A* não troca qualidade por velocidade.
- A* finalizou 44 vértices contra 344 (87,2% menos). Em consultas repetidas em grafos maiores, esse é o ganho que escala: o esforço de exploração cai aproximadamente na mesma proporção.
- O tempo mediano caiu de 1,103 ms para 0,283 ms (3,89×; 74,3% menos). Em valores absolutos, a diferença é de frações de milissegundo para uma única consulta; o argumento é de eficiência algorítmica, não de ganho financeiro.
- O caminho tem 17 arestas, com média de 122,3 m por aresta.

### Limitações da análise

- Não há dados de custo por quilômetro, combustível, salário ou multas; portanto, **não é possível afirmar economia financeira** com este experimento. O impacto medido é distância e esforço computacional.
- As coordenadas Amazon são anonimizadas/perturbadas; a origem foi associada a um nó a 158,54 m e o destino a 30,16 m. O caminho é uma aproximação da rota real.
- O experimento resolve um único trecho origem–destino. Não reproduz a rota completa do motorista nem compara com a operação sem otimização.
- O peso é distância (`length`), não tempo de viagem; não há trânsito, janelas de entrega ou capacidade.
- A heurística Haversine é admissível para pesos em metros. Se o peso fosse tempo de viagem, seria necessário converter a heurística ou usar `h = 0`.

### Análise de sensibilidade (ilustrativa)

O custo unitário da operação não foi fornecido e, por isso, os valores abaixo são **hipotéticos**: servem para mostrar como converter distância em custo no dia em que o dado real estiver disponível, não como resultado do experimento.

$$
\text{custo do trecho} = \text{distância (km)} \times \text{custo por km}
$$

Com a rota ótima de 2,0794 km:

| Custo por km | Custo do trecho | Economia a cada 100 m evitados |
|---:|---:|---:|
| R$ 1,00 | R$ 2,08 | R$ 0,10 |
| R$ 3,00 | R$ 6,24 | R$ 0,30 |
| R$ 5,00 | R$ 10,40 | R$ 0,50 |

Cenário também hipotético: se a rota usada hoje fosse 10% mais longa (2.287,36 m, valor **não medido**), a rota ótima economizaria 207,94 m por entrega — o equivalente a R$ 0,21 por entrega com custo de R$ 1,00/km (R$ 1,04 com R$ 5,00/km). Para 1.000 entregas nesse mesmo padrão, a faixa seria de R$ 208 a R$ 1.040. Basta substituir o custo por km e o volume de entregas pelos números reais da operação; sem eles, esses valores **não** devem ser apresentados como economia comprovada.

### Decisão recomendada

Para consultas ponto a ponto, adotar **A\***: entrega a mesma rota ótima com menos vértices finalizados e menor tempo. Manter **Dijkstra** como referência de validação e como alternativa quando não houver heurística admissível para o peso escolhido. Antes de usar em produção, validar os pesos e a unidade da heurística, e tratar as coordenadas como aproximadas.

## 13. Testes e demonstração sintética

Os 14 testes automatizados não precisam consultar a internet e não representam resultados experimentais da Amazon. Eles cobrem:

- `tests/test_algoritmos.py`: mesmo custo ótimo, respeito à direção das arestas, rejeição de pesos negativos e eventos do `--trace`;
- `tests/test_amazon_data_loader.py`: origem pela parada `Station`, CSV auxiliar, precedência de `--origin-coordinates`, rota sem origem, múltiplos `Dropoff`, múltiplas `Station`, leitura do JSON e listagens.

Execute:

```bash
python -m unittest discover -s tests -v
```

Também existe uma demonstração isolada em um pequeno grafo sintético:

```bash
python main.py --demo
```

Use `--demo` apenas para verificar a lógica dos algoritmos. Não apresente os resultados desse modo como resultados obtidos com o dataset Amazon.

## 14. Critérios de avaliação e interpretação

- Dijkstra e A* recebem o mesmo grafo direcionado, a mesma origem e o mesmo destino.
- Os custos das arestas são os comprimentos OSM `length`, em metros. O objetivo é minimizar distância, não tempo de viagem.
- A heurística do A* é a distância Haversine em metros. Sua admissibilidade depende de os pesos `length` não serem inferiores à distância Haversine (linha reta) entre os nós extremos das arestas.
- O tempo de busca é medido com `time.perf_counter()`. O relatório apresenta mediana e média das repetições para reduzir o impacto de variações ocasionais em medições muito pequenas.
- O contador de vértices explorados considera os nós retirados da fila de prioridade e finalizados, incluindo origem e destino.
- A* pode explorar menos vértices que Dijkstra, mas isso não é garantido em todos os grafos.
- Coordenadas Amazon anonimizadas/perturbadas tornam aproximada a associação com a malha viária OSM. Essa limitação deve ser mencionada na apresentação.
- O projeto resolve apenas um trecho origem-destino. Não reproduz a sequência de todas as entregas de uma rota histórica Amazon.

## 15. Git: o que deve ser versionado

Versione o código-fonte, testes, documentação e arquivos de configuração. Não versione o ambiente virtual, o JSON completo do dataset, grafos OSM em cache ou resultados volumosos gerados localmente.

O `.gitignore` do projeto já deve excluir, entre outros:

```gitignore
.venv/
__pycache__/
*.py[cod]
.DS_Store
*.log
cache/osm_graphs/*
!cache/osm_graphs/.gitkeep
cache/*.json
results/*
!results/.gitkeep
data/amazon/*.json
```

**Observação sobre este repositório:** o arquivo `data/amazon/route_data.json` (78 MB) e dois dumps HTTP do OSMnx em `cache/` já estão versionados para permitir a execução offline da entrega. Em um repositório público, remova-os do índice com `git rm --cached` e baixe o dataset com `download_amazon_data.py`; se o tamanho do histórico for um problema, será necessário reescrevê-lo.

Antes de realizar o commit, confira:

```bash
git status
python -m unittest discover -s tests -v
```

## 16. Referências e licença dos dados

- Amazon Open Data Registry — 2021 Amazon Last Mile Routing Research Challenge Dataset: <https://registry.opendata.aws/amazon-last-mile-challenges/>
- MIT-CAVE — documentação do formato dos arquivos: <https://github.com/MIT-CAVE/rc-cli/blob/main/templates/data_structures.md>
- Merchán, D.; Arora, J.; Pachon, J.; Konduri, K.; Winkenbach, M.; Parks, S.; Noszek, J. (2022). *2021 Amazon Last Mile Routing Research Challenge: Data Set*. Transportation Science. <https://doi.org/10.1287/trsc.2022.1173>
- OSMnx — documentação: <https://osmnx.readthedocs.io/>

A base Amazon é disponibilizada sob licença Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0). Confira as condições da licença antes de redistribuir os dados ou utilizá-los para fins comerciais.
