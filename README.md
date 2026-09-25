# Dashboard de desigualdades de saneamento no Ceará — 2022

Projeto de Ciência de Dados que integra informações de abastecimento de água,
esgotamento sanitário, destino do lixo, população, área e densidade dos 184
municípios do Ceará.

O produto principal é um aplicativo Streamlit com indicadores, mapas,
rankings e cruzamentos exploratórios construídos a partir de dados do
SIDRA/IBGE e da malha municipal de 2022.

> **Importante:** os indicadores de déficit e o índice combinado são
> construções metodológicas da equipe. Eles não são indicadores oficiais do
> IBGE.

---

## Sumário

1. [Objetivo](#objetivo)
2. [Fontes de dados](#fontes-de-dados)
3. [Estrutura dos dados SIDRA](#estrutura-dos-dados-sidra)
4. [Como executar](#como-executar)
5. [Bibliotecas](#bibliotecas)
6. [Fluxo completo do aplicativo](#fluxo-completo-do-aplicativo)
7. [Localização dos arquivos](#localização-dos-arquivos)
8. [Leitura e tratamento inicial](#leitura-e-tratamento-inicial)
9. [Transformação das tabelas](#transformação-das-tabelas)
10. [Integração das quatro bases](#integração-das-quatro-bases)
11. [Construção dos indicadores](#construção-dos-indicadores)
12. [Índice exploratório de déficit](#índice-exploratório-de-déficit)
13. [Medidas complementares](#medidas-complementares)
14. [Classificação dos municípios](#classificação-dos-municípios)
15. [Interface e filtros](#interface-e-filtros)
16. [Mapas e análise territorial](#mapas-e-análise-territorial)
17. [Os nove insights](#os-nove-insights)
18. [Leitura das categorias](#leitura-das-categorias)
19. [Validações](#validações)
20. [Pontos de atenção](#pontos-de-atenção)
21. [Limitações](#limitações)
22. [Estrutura do projeto](#estrutura-do-projeto)

---

## Objetivo

O aplicativo procura responder:

> Onde estão os maiores déficits de água, esgotamento sanitário e destino do
> lixo no Ceará, e quais municípios merecem investigação prioritária quando
> essas dimensões são analisadas em conjunto?

Para responder, o projeto:

- padroniza quatro tabelas diferentes;
- seleciona a mesma granularidade municipal;
- transforma categorias em variáveis analíticas;
- integra as fontes pelo código oficial do município;
- valida a cardinalidade das junções;
- calcula indicadores proporcionais e absolutos;
- cria um índice exploratório multidimensional;
- produz mapas e gráficos interativos;
- apresenta associações sem tratá-las como relações causais.

O trabalho é descritivo e exploratório. Não utiliza aprendizado de máquina,
previsão ou inferência causal.

---

## Fontes de dados

| Tabela/arquivo | Conteúdo | Unidade principal |
|---|---|---|
| SIDRA 6803 | Ligação à rede geral e principal forma de abastecimento de água | Domicílios |
| SIDRA 6805 | Tipo de esgotamento sanitário | Domicílios |
| SIDRA 6892 | Destino do lixo | Domicílios |
| SIDRA 4714 | População, área territorial e densidade demográfica | Pessoas, km² e hab./km² |
| Malha municipal | Polígonos dos municípios do Ceará | Geometrias |

Todos os dados são referentes a 2022. As três tabelas de saneamento usam como
universo os **domicílios particulares permanentes ocupados**. Por isso, seus
percentuais usam domicílios como denominador, e não população residente.

Os arquivos originais estão preservados em `dados/raw`. O aplicativo apenas os
lê e realiza as transformações em memória.

---

## Estrutura dos dados SIDRA

### Granularidade original

Nos arquivos de saneamento, uma linha representa:

```text
nível territorial
+ território
+ variável
+ ano
+ categoria
+ unidade
+ valor
```

O mesmo município aparece várias vezes porque cada categoria ocupa uma linha.
Isso não significa duplicidade.

| Tabela | Linhas por município | Motivo |
|---:|---:|---|
| 6803 | 4 | Total e três categorias de água |
| 6805 | 9 | Total e oito categorias de esgoto |
| 6892 | 7 | Total e seis categorias de lixo |
| 4714 | 3 | População, área e densidade |

A chave original das tabelas de saneamento é:

```text
NC + D1C + D2C + D3C + D4C
```

Na tabela 4714, que não possui uma categoria `D4C`, a chave é:

```text
NC + D1C + D2C + D3C
```

### Colunas principais

| Coluna | Significado |
|---|---|
| `NC` | Código do nível territorial |
| `NN` | Nome do nível territorial |
| `D1C` | Código do território |
| `D1N` | Nome do território |
| `D2C` / `D2N` | Código e nome da variável |
| `D3C` / `D3N` | Código e descrição do ano |
| `D4C` / `D4N` | Código e descrição da categoria |
| `MC` / `MN` | Código e nome da unidade |
| `V` | Valor observado |

### Linha descritiva adicional

Os CSVs contêm nomes curtos na primeira linha e descrições completas na
segunda. Os dados começam na terceira linha. A leitura ignora a segunda linha,
pois ela não é uma observação.

---

## Como executar

### 1. Entrar na pasta do projeto

```bash
cd /home/joaovlopess/facul_s7/ciencia_dados/Trabalho1Saneamento
```

### 2. Ativar o ambiente virtual

```bash
source venv/bin/activate
```

### 3. Instalar as dependências

```bash
python -m pip install -r requirements.txt
```

### 4. Executar o aplicativo

O arquivo documentado neste README é `app.py`. Como o nome contém espaço e
parênteses, use aspas:

```bash
streamlit run "app.py"
```

Sem ativar o ambiente virtual:

```bash
venv/bin/streamlit run "app.py"
```

O Streamlit exibirá um endereço semelhante a:

```text
http://localhost:8501
```

Para encerrar, pressione `Ctrl+C` no terminal.

---

## Bibliotecas

| Biblioteca | Função no projeto |
|---|---|
| Streamlit | Interface, filtros, cartões, abas e apresentação |
| pandas | Leitura, limpeza, pivoteamento, junções e indicadores |
| Plotly Express | Barras, dispersões, matriz de correlação e mapas |
| GeoPandas | Leitura e tratamento da malha geográfica |
| pathlib | Localização dos arquivos |

As funções de leitura e preparação recebem `@st.cache_data`. O cache evita que
os CSVs e a malha sejam processados novamente a cada interação com os filtros.

---

## Fluxo completo do aplicativo

```text
1. Localizar os cinco arquivos necessários
                     ↓
2. Ler os quatro CSVs do SIDRA
                     ↓
3. Remover a linha descritiva e converter valores
                     ↓
4. Manter somente NC = 6 (municípios)
                     ↓
5. Pivotear cada tabela para uma linha por município
                     ↓
6. Renomear categorias por códigos oficiais
                     ↓
7. Unir água, esgoto, lixo e contexto territorial
                     ↓
8. Validar cardinalidade e correspondências
                     ↓
9. Calcular percentuais e índice combinado
                     ↓
10. Criar medidas absolutas e grupos de desempenho
                     ↓
11. Aplicar filtros interativos
                     ↓
12. Integrar indicadores à malha
                     ↓
13. Produzir mapas, rankings e cruzamentos
```

---

## Localização dos arquivos

O código define uma raiz e procura os arquivos recursivamente pelo nome. Os
caminhos são reunidos em `CAMINHOS`, com as chaves:

```text
agua, esgoto, lixo, pop e malha
```

Se um arquivo não for encontrado, a execução é interrompida com
`FileNotFoundError`.

### Intenção dessa estratégia

- evitar caminhos absolutos de um único computador;
- centralizar as fontes;
- facilitar a movimentação do projeto;
- detectar arquivos ausentes antes dos cálculos.

### Atenção

`app.py` usa:

```python
RAIZ = Path(__file__).resolve().parent.parent
```

Essa expressão foi pensada para um arquivo colocado em `app/app.py`. Como a
versão atual está na raiz do projeto, a busca começa uma pasta acima e ainda
encontra os dados por ser recursiva. Uma versão definitiva deveria usar a pasta
real do projeto explicitamente. Também não devem existir cópias diferentes com
o mesmo nome, pois `_achar()` utiliza o primeiro resultado encontrado.

---

## Leitura e tratamento inicial

A função `ler_tabela()` é reutilizada para os quatro CSVs.

### Regras de leitura

- separador `;`;
- todas as colunas inicialmente como texto;
- valores vazios preservados até o tratamento explícito;
- segunda linha ignorada;
- coluna `V` convertida para número;
- código `D1C` preenchido para sete caracteres;
- somente linhas municipais (`NC == "6"`) mantidas.

### Por que carregar códigos como texto?

Códigos são identificadores, não quantidades. Mantê-los como texto evita
operações matemáticas sem sentido, perda de zeros e incompatibilidade com a
chave `codarea` da malha.

### Símbolos especiais

Foram encontrados:

- 15 símbolos `-` na tabela 6805;
- 5 símbolos `-` na tabela 6892;
- nenhum `X`, `..` ou `...`.

Nesses arquivos, `-` significa zero absoluto.

Na implementação atual de `app.py`, `-` é transformado temporariamente em
`pd.NA` e depois tratado como zero com `fillna(0)` nos cálculos. O efeito
numérico dos indicadores é zero, mas a representação intermediária mistura
zero com ausência. O tratamento conceitualmente mais claro seria substituir
`-` diretamente por `0`.

---

## Transformação das tabelas

### Formato longo e formato largo

Originalmente:

| Município | Categoria | Valor |
|---|---|---:|
| A | Total | 10.000 |
| A | Sem rede | 2.000 |
| A | Com rede | 8.000 |

Depois do `pivot_table()`:

| Município | Total | Sem rede | Com rede |
|---|---:|---:|---:|
| A | 10.000 | 2.000 | 8.000 |

Cada município passa a ocupar uma linha. Isso torna possível integrar as
fontes em uma relação um para um.

O pivoteamento utiliza `aggfunc="first"`. Essa escolha depende da validação
prévia de que não existem duplicatas na chave. Se houvesse duplicatas, manter o
primeiro valor poderia esconder inconsistências.

### Água — tabela 6803

| Código | Categoria | Coluna analítica |
|---:|---|---|
| 72129 | Total | `agua_total` |
| 72144 | Ligação à rede e uso como principal | `agua_rede_usa` |
| 72145 | Ligação, mas outra forma como principal | `agua_rede_outra` |
| 72153 | Sem ligação à rede geral | `agua_sem_rede` |

O nome `D1N` é renomeado para `municipio` e preservado nessa tabela.

### Esgoto — tabela 6805

| Código | Categoria | Coluna analítica |
|---:|---|---|
| 46292 | Total | `esg_total` |
| 72110 | Rede geral ou pluvial | `esg_rede` |
| 72111 | Fossa séptica ligada | `esg_fossa_lig` |
| 72112 | Fossa séptica não ligada | `esg_fossa_nlig` |
| 72113 | Fossa rudimentar ou buraco | `esg_rudimentar` |
| 92858 | Vala | `esg_vala` |
| 72114 | Rio, lago, córrego ou mar | `esg_rio` |
| 72115 | Outra forma | `esg_outra` |
| 92861 | Sem banheiro nem sanitário | `esg_sem_ban` |

### Lixo — tabela 6892

| Código | Categoria | Coluna analítica |
|---:|---|---|
| 10972 | Total | `lixo_total` |
| 72120 | Coletado no domicílio | `lixo_coletado_dom` |
| 72121 | Depositado em caçamba | `lixo_cacamba` |
| 72122 | Queimado | `lixo_queimado` |
| 72123 | Enterrado | `lixo_enterrado` |
| 72124 | Terreno baldio, encosta ou área pública | `lixo_terreno_baldio` |
| 1091 | Outro destino | `lixo_outro` |

### População e território — tabela 4714

| Código | Variável | Coluna analítica |
|---:|---|---|
| 93 | População residente | `populacao` |
| 6318 | Área territorial | `area_km2` |
| 614 | Densidade demográfica | `densidade` |

### Por que usar os códigos?

A transformação é definida por códigos oficiais, não por busca de palavras nos
textos. Isso evita problemas de acentuação, abreviação e alterações de redação,
além de tornar cada correspondência explícita e auditável.

---

## Integração das quatro bases

A chave de integração é `D1C`, código municipal do IBGE com sete dígitos.

As junções ocorrem nesta ordem:

```text
água + esgoto + lixo + população/área/densidade
```

### Junção externa

`how="outer"` preserva municípios que eventualmente apareçam em apenas uma
fonte. Isso evita que uma incompatibilidade seja descartada silenciosamente.

### Validação um para um

`validate="one_to_one"` exige no máximo uma linha por município em cada lado.
Se uma chave estiver duplicada, a execução falha em vez de multiplicar linhas.

### Indicadores de correspondência

Cada junção produz temporariamente uma coluna com:

- `both`: código nos dois lados;
- `left_only`: somente à esquerda;
- `right_only`: somente à direita.

Essas colunas formam `relatorio_join` e são removidas da base analítica.

### Resultado observado

| Controle | Resultado |
|---|---:|
| Água | 184 municípios |
| Esgoto | 184 municípios |
| Lixo | 184 municípios |
| População | 184 municípios |
| Base integrada | 184 municípios |
| Sem correspondência nas junções | 0 |

---

## Construção dos indicadores

### Água sem rede geral

```text
pct_agua_sem_rede =
100 × agua_sem_rede / agua_total
```

Mede ausência de ligação à rede geral. Não mede potabilidade, continuidade ou
qualidade do abastecimento.

### Esgoto em rede geral ou pluvial

```text
pct_esgoto_rede =
100 × esg_rede / esg_total
```

Representa a categoria oficial “rede geral ou pluvial”. Não comprova
tratamento efetivo do esgoto.

### Esgoto inadequado — definição operacional

```text
pct_esgoto_inadequado = 100 ×
(esg_rudimentar + esg_vala + esg_rio + esg_sem_ban)
/ esg_total
```

Entram no indicador:

- fossa rudimentar ou buraco;
- vala;
- rio, lago, córrego ou mar;
- ausência de banheiro ou sanitário.

Fossa séptica não ligada e outra forma permanecem indefinidas e não entram no
indicador atual.

### Lixo inadequado — definição operacional

```text
pct_lixo_inadequado = 100 ×
(lixo_queimado + lixo_enterrado + lixo_terreno_baldio)
/ lixo_total
```

“Outro destino” não entra por não informar qual forma foi utilizada.

### Média dos percentuais municipais

Os KPIs do aplicativo usam:

```python
base["percentual"].mean()
```

Isso calcula a média simples dos 184 percentuais. Cada município recebe o mesmo
peso. A interpretação correta é:

> percentual médio de um município cearense.

Não representa diretamente a porcentagem de todos os domicílios do Ceará. Para
essa segunda pergunta seria necessário dividir a soma dos numeradores pela soma
dos denominadores.

Resultados da média municipal:

| Indicador | Média municipal |
|---|---:|
| Água sem rede geral | 23,33% |
| Esgoto inadequado, definição selecionada | 57,35% |
| Lixo inadequado, definição selecionada | 25,41% |

---

## Índice exploratório de déficit

```text
indice_deficit =
(pct_agua_sem_rede
 + pct_esgoto_inadequado
 + pct_lixo_inadequado) / 3
```

Cada dimensão recebe peso igual de um terço.

### Interpretação

- valores menores: menor presença conjunta dos déficits selecionados;
- valores maiores: maior acúmulo dessas situações;
- faixa teórica: 0 a 100.

### Limitações

- não é indicador oficial;
- usa pesos iguais sem validação externa;
- depende das categorias selecionadas;
- não mede qualidade dos serviços;
- não considera diretamente a quantidade de domicílios afetados;
- não deve definir sozinho prioridade de investimento.

Os cinco maiores índices no conjunto completo são Salitre, Choró, Ibaretama,
Abaiara e Amontada.

---

## Medidas complementares

### Quantidade absoluta de domicílios no déficit de esgoto

```text
domicilios_deficit_esgoto =
esg_rudimentar + esg_vala + esg_rio + esg_sem_ban
```

### Concentração por área

```text
deficit_esgoto_por_km2 =
domicilios_deficit_esgoto / area_km2
```

Essas medidas distinguem três perspectivas:

| Medida | Pergunta |
|---|---|
| Percentual | Qual parcela dos domicílios está afetada? |
| Quantidade | Quantos domicílios estão afetados? |
| Por km² | Qual é a concentração territorial média? |

A área utilizada é a área total municipal, não apenas a área urbanizada.

---

## Classificação dos municípios

Os municípios recebem uma categoria com base no índice:

| Categoria | Regra | Quantidade |
|---|---|---:|
| Entre os 10 melhores | Dez menores índices | 10 |
| Entre os 10 piores | Dez maiores índices | 10 |
| Próximo da média estadual | Dez índices mais próximos da média, excluindo os grupos anteriores | 10 |
| Demais municípios | Restantes | 154 |

A distância até a média é:

```text
dist_media = |indice_deficit - média municipal do índice|
```

A classificação é calculada sobre os 184 municípios antes dos filtros. Assim,
seu significado não muda quando o usuário seleciona um recorte.

“Melhor” significa apenas menor índice dentro dessa metodologia, não saneamento
ideal ou universal.

---

## Interface e filtros

O aplicativo apresenta:

- título e pergunta orientadora;
- relatório expansível das junções;
- cartões de indicadores;
- filtro por faixa populacional;
- seleção de municípios específicos;
- mapa combinado;
- mapas isolados;
- ranking de prioridade;
- seis abas de cruzamentos;
- revisão das categorias de esgoto;
- fontes e limitações.

O recorte filtrado é criado a partir de uma cópia da base. Se nenhum município
atender aos filtros, o Streamlit interrompe os gráficos e exibe um aviso.

---

## Mapas e análise territorial

A malha é carregada com GeoPandas. O código `codarea` é convertido para texto e
as geometrias recebem `make_valid()`.

Essa correção é necessária porque cinco municípios têm pequenas
auto-interseções:

- Acaraú;
- Barbalha;
- Crateús;
- Limoeiro do Norte;
- Mauriti.

O arquivo bruto permanece intacto.

### Integração com a malha

```text
D1C, na base analítica ↔ codarea, na malha
```

### Mapas disponíveis

- índice combinado;
- água sem rede;
- esgoto inadequado;
- lixo inadequado.

Cada mapa isolado usa sua própria escala de cor. As cores de abas diferentes
não devem ser comparadas diretamente.

O mapa fornece leitura visual. Nenhum teste formal de autocorrelação ou cluster
espacial é aplicado.

### Distância até Fortaleza

As geometrias são projetadas para EPSG:3857, seus centroides são calculados e a
distância ao centroide de Fortaleza é convertida para quilômetros.

É uma aproximação em linha reta, não distância rodoviária ou tempo de viagem.

---

## Os oito insights

### Insight 1 — Esgoto é o principal gargalo

Os KPIs comparam as médias municipais de água sem rede, esgoto inadequado e
lixo inadequado.

O cartão de esgoto inadequado usa as quatro categorias selecionadas e resulta
em 57,35%. Entretanto, o gráfico comparativo usa:

```text
100 - média do percentual em rede geral ou pluvial
```

que resulta em 80,73%. Essa medida representa tudo que está fora de rede geral
ou pluvial, incluindo categorias não classificadas como inadequadas.

A afirmação de que esgoto está 3,46 vezes pior que água usa 80,73 ÷ 23,33. Ela
não usa o mesmo indicador do cartão. Essa diferença deve ser corrigida ou
explicada explicitamente.

### Insight 2 — Descompasso entre água e esgoto

```text
gap_agua_esgoto =
pct_esgoto_inadequado - pct_agua_sem_rede
```

Valores positivos indicam que a proporção classificada como esgoto inadequado
é maior que a proporção sem rede de água. O gap é uma assimetria exploratória;
não demonstra cronologia de investimentos.

### Insight 3 — Distância até Fortaleza

Compara a distância entre centroides com o percentual em rede geral ou
pluvial. A correlação é calculada novamente para o recorte filtrado.

Correlação próxima de zero indica ausência de relação linear clara, não prova
que localização seja irrelevante.

### Insight 4 — Lixo e densidade

Os municípios são divididos em até quatro grupos de densidade com `qcut`. O
gráfico compara a média municipal de lixo inadequado de cada grupo.

O padrão sugere maior participação das formas selecionadas em municípios menos
densos. A frase do aplicativo que atribui isso à falta de coleta regular deve
ser tratada como hipótese, não como causalidade comprovada.

### Insight 5 — Padrão geográfico

O mapa localiza municípios com maiores valores do índice. Proximidade visual
entre cores não comprova cluster espacial. Seria necessário um método espacial
formal para essa conclusão.

### Insight 6 — Oito categorias de esgoto

As categorias são agregadas e coloridas como:

- adequado;
- indefinido;
- inadequado.

Fossa não ligada e outra forma permanecem indefinidas. Alterar essa decisão
modificaria `pct_esgoto_inadequado` e `indice_deficit`.

### Insight 7 — Paradoxo de Fortaleza

Cruza área territorial com quantidade absoluta do déficit de esgoto. Fortaleza
possui aproximadamente:

- 10,72% na definição de esgoto inadequado;
- 92.204 domicílios nessas categorias;
- 295,19 domicílios em déficit por km².

O insight demonstra que uma taxa relativamente baixa pode coexistir com uma
grande quantidade e concentração absoluta.

### Insight 8 — Até os melhores têm esgoto ruim

Seleciona os dez menores índices e compara as três dimensões. Nesse grupo, as
médias são aproximadamente:

| Dimensão | Média |
|---|---:|
| Água sem rede | 6,42% |
| Esgoto inadequado | 19,42% |
| Lixo inadequado | 6,36% |

O esgoto é aproximadamente 3,04 vezes a média de água e lixo nesse grupo.

Esse insight não é um novo cruzamento independente: o grupo foi definido pelo
próprio índice que contém esgoto. Ele deve ser apresentado como reforço
descritivo, não validação externa.

---

## Leitura das categorias

### Água

| Categoria | Leitura operacional |
|---|---|
| Usa rede como principal | Referência; não comprova qualidade |
| Possui rede, mas usa outra forma | Intermediária |
| Sem rede geral | Incluída no déficit |
| Total | Denominador |

### Esgoto

| Categoria | Leitura operacional |
|---|---|
| Rede geral ou pluvial | Fora do déficit; não comprova tratamento |
| Fossa ligada | Fora do déficit atual |
| Fossa não ligada | Indefinida |
| Fossa rudimentar | Incluída no déficit |
| Vala | Incluída no déficit |
| Rio, lago, córrego ou mar | Incluída no déficit |
| Outra forma | Indefinida |
| Sem banheiro | Incluída no déficit |
| Total | Denominador |

### Lixo

| Categoria | Leitura operacional |
|---|---|
| Coletado no domicílio | Referência; destino final desconhecido |
| Depositado em caçamba | Referência; destino final desconhecido |
| Queimado | Incluído no déficit |
| Enterrado | Incluído no déficit |
| Terreno baldio/encosta/área pública | Incluído no déficit |
| Outro destino | Indefinido |
| Total | Denominador |

“Fora do déficit” não significa automaticamente “adequado”. Significa apenas
que a categoria não foi somada ao indicador atual.

---

## Validações

Foram verificados:

- 184 municípios em todas as fontes;
- conjuntos territoriais idênticos;
- nenhuma duplicata completa;
- nenhuma duplicata nas chaves lógicas;
- nenhuma célula vazia nos arquivos originais;
- códigos e nomes com correspondência consistente;
- categorias componentes fechando exatamente o Total;
- totais domiciliares iguais nas três tabelas de saneamento;
- densidade compatível com população dividida pela área;
- nenhuma incompatibilidade nas junções;
- 184 linhas e 184 códigos únicos na base integrada.

---

## Pontos de atenção

### 1. Zero absoluto e ausência

O código converte `-` para `pd.NA` antes de tratá-lo como zero. O resultado dos
indicadores atuais é preservado por `fillna(0)`, mas ausências verdadeiras
também seriam convertidas para zero nesses cálculos. A implementação ideal deve
distinguir as duas situações desde a leitura.

### 2. Média municipal e percentual estadual

```python
base["percentual"].mean()
```

é matematicamente correto para descrever o município médio. Não representa o
percentual de todos os domicílios do Ceará, que exigiria a razão entre somas.

### 3. Duas definições diferentes de esgoto

- cartão: quatro categorias selecionadas como inadequadas;
- gráfico: tudo que não está em rede geral ou pluvial.

Essas medidas não devem receber o mesmo rótulo.

### 4. Total e componentes

A categoria Total não deve ser somada às categorias componentes, pois isso
duplicaria os domicílios.

### 5. Linguagem causal

O aplicativo encontra associações. Expressões como “provavelmente por falta de
coleta” devem ser apresentadas como hipóteses.

### 6. Filtros e correlações

As correlações das abas são recalculadas sobre o recorte atual. Selecionar
poucos municípios pode produzir valores instáveis ou `NaN`.

---

## Limitações

- somente o ano de 2022 é analisado;
- ligação à rede de água não mede regularidade ou potabilidade;
- rede geral ou pluvial não comprova tratamento de esgoto;
- destino declarado do lixo não informa destino final após a coleta;
- duas categorias de esgoto continuam indefinidas;
- “outro destino” do lixo não entra no déficit;
- o índice aplica pesos iguais;
- rankings proporcionais não mostram quantidade absoluta;
- déficit por km² usa a área municipal total;
- distância até Fortaleza é aproximada entre centroides;
- o mapa não executa teste de cluster espacial;
- correlação não permite concluir causalidade;
- o mapa-base Carto pode depender de conexão com a internet.

---

## Estrutura do projeto

```text
Trabalho1Saneamento/
├── app.py
├── requirements.txt
├── README.md
├── dados/
│   └── raw/
│       ├── fontes.csv
│       ├── dados_originais/
│       │   ├── t4714_populacao_area_densidade_2022_ce_br.csv
│       │   ├── t6803_abastecimento_agua_2022_ce_br.csv
│       │   ├── t6805_esgotamento_sanitario_2022_ce_br.csv
│       │   └── t6892_destino_lixo_2022_ce_br.csv
│       └── dados_comuns/
│           └── malha_municipal_ce_2022.geojson
└── visualizador_dados/
```

---

## Síntese metodológica

> As quatro tabelas do SIDRA foram carregadas como texto, tiveram a linha
> descritiva removida, os valores convertidos para formato numérico e os códigos
> municipais padronizados. Foram mantidos somente os 184 municípios. As bases
> originalmente longas foram pivoteadas para que cada município ocupasse uma
> linha e cada categoria se tornasse uma variável. Os códigos oficiais do SIDRA
> foram usados para renomear e classificar as categorias. Água, esgoto, lixo e
> contexto territorial foram unidos pelo código IBGE com junções externas e
> cardinalidade um para um. Todos os municípios encontraram correspondência.
> Sobre a base integrada foram calculados percentuais municipais, um índice
> exploratório de déficit com pesos iguais, medidas absolutas, concentração por
> área e categorias de desempenho. O Streamlit utiliza essa base para produzir
> filtros, mapas, rankings, correlações e análises exploratórias, sempre com a
> ressalva de que as classificações são decisões da equipe e não indicadores
> oficiais do IBGE.
