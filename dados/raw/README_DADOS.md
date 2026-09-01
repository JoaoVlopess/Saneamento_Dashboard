# Equipe 04 — Saneamento domiciliar

Este diretório contém respostas brutas da API oficial do SIDRA, preparadas para uso local pelos alunos. Não há dados limpos, cruzamentos, índices compostos ou conclusões analíticas.

## Arquivos

| Tabela | Arquivo | Conteúdo |
|---|---|---|
| [6803](https://sidra.ibge.gov.br/tabela/6803) | `dados_originais/t6803_abastecimento_agua_2022_ce_br.csv` | Ligação à rede geral e principal forma de abastecimento de água |
| [6805](https://sidra.ibge.gov.br/tabela/6805) | `dados_originais/t6805_esgotamento_sanitario_2022_ce_br.csv` | Tipo de esgotamento sanitário |
| [6892](https://sidra.ibge.gov.br/tabela/6892) | `dados_originais/t6892_destino_lixo_2022_ce_br.csv` | Destino do lixo |
| [4714](https://sidra.ibge.gov.br/tabela/4714) | `dados_originais/t4714_populacao_area_densidade_2022_ce_br.csv` | População, área territorial e densidade demográfica |

Todos os arquivos são de 2022 e incluem Brasil, Ceará e os 184 municípios cearenses.

## Formato dos CSVs

Os arquivos foram retornados diretamente pelo SIDRA em UTF-8, separados por ponto e vírgula. A primeira linha contém nomes curtos (`NC`, `NN`, `D1C`, `D1N`, ..., `MC`, `MN`, `V`), a segunda contém rótulos descritivos e os dados começam na terceira.

```python
import pandas as pd

df = pd.read_csv(
    "dados_originais/arquivo.csv",
    sep=";",
    header=0,
    skiprows=[1],
    dtype=str,
    keep_default_na=False,
)
```

- `NC`/`NN`: código e nome do nível territorial;
- `D1C`/`D1N`: código e nome do território;
- `D2C`/`D2N`: variável;
- `D3C`/`D3N`: ano;
- `D4C`/`D4N`: classificação de saneamento, quando existente;
- `MC`/`MN`: unidade de medida;
- `V`: valor.

A chave bruta deve combinar `NC` e todas as colunas `DnC`. Preserve códigos como texto e não faça junções por nome.

## Seleções concretas

### Tabela 6803 — Água

- Variável 381: Domicílios particulares permanentes ocupados.
- Categorias: Total (72129); possui ligação à rede e a utiliza como principal (72144); possui ligação, mas utiliza principalmente outra forma (72145); não possui ligação com a rede geral (72153).
- As três categorias de nível 1 são mutuamente exclusivas e fecham o Total.

### Tabela 6805 — Esgotamento sanitário

- Variável 381: Domicílios particulares permanentes ocupados.
- Total (46292) e categorias-folha: rede geral ou pluvial (72110); fossa séptica ou fossa filtro ligada à rede (72111); fossa séptica ou fossa filtro não ligada à rede (72112); fossa rudimentar ou buraco (72113); vala (92858); rio, lago, córrego ou mar (72114); outra forma (72115); não tinham banheiro nem sanitário (92861).
- O agregado intermediário 46290 não foi incluído, evitando dupla contagem com 72110 e 72111.

### Tabela 6892 — Lixo

- Variável 381: Domicílios particulares permanentes ocupados.
- Total (10972) e categorias-folha: coletado no domicílio (72120); depositado em caçamba (72121); queimado (72122); enterrado (72123); jogado em terreno baldio, encosta ou área pública (72124); outro destino (1091).
- O agregado intermediário `Coletado` (2520) não foi incluído, evitando dupla contagem.

### Tabela 4714 — Contexto territorial

- Variáveis: População residente (93), Área da unidade territorial (6318) e Densidade demográfica (614).
- Sem classificações adicionais.

## Símbolos e limitações

- `-` significa zero absoluto e deve ser convertido para zero apenas na limpeza. Foram encontrados 15 casos em 6805 e 5 em 6892; não foram encontrados `...`, `..` ou `X`.
- Categorias `Total` e componentes coexistem para conferência. Não some o Total novamente aos componentes.
- Os percentuais de saneamento devem usar o total de domicílios da respectiva tabela, não a população da tabela 4714.
- Ligação à rede de água não informa regularidade, qualidade ou potabilidade.
- Destino do esgoto não comprova tratamento. A categoria “rede geral ou pluvial” não deve ser rotulada automaticamente como tratamento adequado.
- Destino do lixo descreve a situação declarada do domicílio, não a destinação final após a coleta.
- Qualquer índice composto criado pela equipe deve ser identificado como construção própria, não como indicador oficial do IBGE.

## Validações executadas

- HTTP 200 em todas as requisições;
- UTF-8, esquema consistente e quantidades de linhas esperadas;
- ano, variável e categorias exatamente iguais às seleções acima;
- Brasil, Ceará e o mesmo conjunto de 184 municípios em todos os arquivos;
- ausência de chaves duplicadas;
- categorias mutuamente exclusivas fecham o Total em 6803, 6805 e 6892;
- total de domicílios idêntico entre as três tabelas de saneamento nos 186 territórios;
- densidade publicada compatível com população dividida pela área, com diferença máxima inferior a 0,005 por arredondamento.

As URLs completas, horários, linhas e hashes SHA-256 estão em `fontes.csv`.
