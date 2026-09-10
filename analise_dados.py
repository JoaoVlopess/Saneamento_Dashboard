from pathlib import Path

import pandas as pd


# Pasta onde estão os arquivos originais
PASTA_RAW = Path("dados/raw/dados_originais")

# Símbolos especiais utilizados pelo SIDRA
SIMBOLOS_SIDRA = ["-", "0", "X", "..", "..."]


def carregar_csv(caminho):
    """
    Carrega o CSV preservando todos os valores como texto.
    O sep=None tenta descobrir automaticamente o separador.
    """

    try:
        return pd.read_csv(
            caminho, #Caminho do arquivo CSV
            sep=None, #BUsca automaticamente o separador do CSV
            engine="python",#Motor de leitura do CSV
            dtype=str,#Mantém todos os valores como texto
            keep_default_na=False,#Mantém os valores vazios como texto
            encoding="utf-8-sig"#Mantém a codificação UTF-8 
        )

    except UnicodeDecodeError:
        return pd.read_csv(
            caminho,
            sep=None,
            engine="python",
            dtype=str,
            keep_default_na=False,
            encoding="latin-1"
        )


def mostrar_valores_unicos(df, coluna, limite=30):
    """
    Mostra os valores diferentes de uma coluna,
    desde que ela não tenha valores demais.

    Recebe :
        df: DataFrame do Pandas
        coluna: nome da coluna a ser inspecionada
        limite: quantidade máxima de valores diferentes a serem exibidos
    """

    valores = (
        df[coluna]
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    valores = [valor for valor in valores if valor != ""]

    print(f"\n{coluna}:")
    print(f"Quantidade de valores diferentes: {len(valores)}")

    if len(valores) <= limite:
        for valor in valores:
            print(f"  - {valor}")
    else:
        print(f"  Primeiros {limite} valores:")
        for valor in valores[:limite]:
            print(f"  - {valor}")


def inspecionar_base(caminho):
    """
    Exibe as principais informações necessárias
    para a ficha de metadados.
    """

    df = carregar_csv(caminho)

    print("\n" + "=" * 70)
    print(f"ARQUIVO: {caminho.name}")
    print("=" * 70)

    # Dimensão da base
    print(f"\nQuantidade de linhas: {df.shape[0]}")
    print(f"Quantidade de colunas: {df.shape[1]}")

    # Nomes das colunas
    print("\nCOLUNAS ENCONTRADAS:")

    for coluna in df.columns:
        print(f"  - {coluna}")

    # Primeiras linhas
    print("\nPRIMEIRAS 5 LINHAS:")
    print(df.head().to_string(index=False))

    # Duplicatas completas
    print("\nDUPLICATAS COMPLETAS:")
    print(df.duplicated().sum())

    # Campos vazios
    print("\nCAMPOS VAZIOS POR COLUNA:")

    for coluna in df.columns:
        quantidade = df[coluna].astype(str).str.strip().eq("").sum()

        if quantidade > 0:
            percentual = quantidade / len(df) * 100

            print(
                f"  - {coluna}: {quantidade} "
                f"({percentual:.2f}%)"
            )

        if quantidade == 0:
            print(f"  - {coluna}: 0")
            continue

    # Símbolos especiais
    print("\nSÍMBOLOS ESPECIAIS DO SIDRA:")

    for simbolo in SIMBOLOS_SIDRA:
        quantidade = 0

        for coluna in df.columns:
            quantidade += (
                df[coluna]
                .astype(str)
                .str.strip()
                .eq(simbolo)
                .sum()
            )

        print(f"  - {simbolo}: {quantidade}")

    # Procura colunas relacionadas aos metadados
    termos_importantes = [
        "ano",
        "período",
        "periodo",
        "variável",
        "variavel",
        "unidade",
        "nível territorial",
        "nivel territorial",
        "forma",
        "tipo",
        "destino"
    ]

    print("\nVARIÁVEIS, UNIDADES E CATEGORIAS:")

    for coluna in df.columns:
        nome_normalizado = coluna.lower()

        if any(termo in nome_normalizado for termo in termos_importantes):
            mostrar_valores_unicos(df, coluna)

    print("\nFIM DA INSPEÇÃO")


# Localiza todos os CSVs dentro de data/raw
arquivos_csv = sorted(PASTA_RAW.glob("*.csv"))

if not arquivos_csv:
    print("Nenhum arquivo CSV foi encontrado em data/raw.")

else:
    print(f"Foram encontrados {len(arquivos_csv)} arquivos CSV.")

    for arquivo in arquivos_csv:
        inspecionar_base(arquivo)