from pathlib import Path
import hashlib
import json

import pandas as pd



PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_RAW = PASTA_PROJETO / "dados" / "raw" / "dados_originais"
PASTA_PROCESSED = PASTA_PROJETO / "dados" / "processed"
PASTA_RELATORIOS = PASTA_PROJETO / "docs" / "qualidade"

MAPA_COLUNAS = {
    "NC": "nivel_territorial_codigo",
    "NN": "nivel_territorial",
    "D1C": "territorio_codigo",
    "D1N": "territorio_nome",
    "D2C": "variavel_codigo",
    "D2N": "variavel",
    "D3C": "ano_codigo",
    "D3N": "ano",
    "D4C": "categoria_codigo",
    "D4N": "categoria",
    "MC": "unidade_codigo",
    "MN": "unidade",
    "V": "valor_original",
}

CONFIGURACOES = {
    "4714": {
        "padrao": "t4714_*.csv",
        "saida": "populacao_area_2022.csv",
        "linhas_esperadas": 558,
        "registros_por_territorio": 3,
    },
    "6803": {
        "padrao": "t6803_*.csv",
        "saida": "agua_2022.csv",
        "linhas_esperadas": 744,
        "registros_por_territorio": 4,
    },
    "6805": {
        "padrao": "t6805_*.csv",
        "saida": "esgoto_2022.csv",
        "linhas_esperadas": 1674,
        "registros_por_territorio": 9,
    },
    "6892": {
        "padrao": "t6892_*.csv",
        "saida": "lixo_2022.csv",
        "linhas_esperadas": 1302,
        "registros_por_territorio": 7,
    },
}

# Categorias detalhadas conhecidas e sem sobreposição.
# Não incluímos "Total" nem subtotais nestas listas.
PARTES_DO_TOTAL = {
    "6803": {"72144", "72145", "72153"},
    "6892": {
        "72120", "72121", "72122",
        "72123", "72124", "72125",
    },
}

# Na tabela de esgoto, precisamos conferir a lista completa
# antes de afirmar quais categorias podem ser somadas.


def carregar_csv(caminho):
    for encoding in ["utf-8-sig", "latin-1"]:
        try:
            df = pd.read_csv(
                caminho,
                sep=None,
                engine="python",
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
            return df, encoding

        except UnicodeDecodeError:
            continue

    raise ValueError(f"Não foi possível ler {caminho.name}")


def preparar_estrutura(df, tabela, relatorio):
    obrigatorias = set(MAPA_COLUNAS)

    if tabela == "4714":
        obrigatorias -= {"D4C", "D4N"}

    faltantes = obrigatorias - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {sorted(faltantes)}"
        )

    relatorio["linhas_carregadas"] = len(df)

    # Detecta a linha explicativa antes de removê-la.
    linha_explicativa = (
        not df.empty
        and df.iloc[0]["NC"].strip()
        == "Nível Territorial (Código)"
        and df.iloc[0]["V"].strip() == "Valor"
    )

    if linha_explicativa:
        df = df.iloc[1:].copy()
    else:
        df = df.copy()

    relatorio["linha_explicativa_removida"] = linha_explicativa

    df = df.rename(columns=MAPA_COLUNAS)

    # Mantém o valor original intacto.
    # Espaços são retirados das demais colunas.
    for coluna in df.columns:
        if coluna != "valor_original":
            df[coluna] = df[coluna].astype("string").str.strip()

    relatorio["duplicatas_completas_removidas"] = int(
        df.duplicated().sum()
    )

    df = df.drop_duplicates().reset_index(drop=True)

    return df


def tratar_valores(df):
    # A normalização ocorre numa série auxiliar.
    original = df["valor_original"].astype("string").str.strip()

    situacoes = {
        "": "ausente",
        "-": "zero_absoluto",
        "X": "valor_inibido",
        "x": "valor_inibido",
        "..": "nao_se_aplica",
        "...": "nao_disponivel",
    }

    df["situacao_valor"] = (
        original.map(situacoes).fillna("disponivel")
    )

    texto_numerico = original.copy()

    ausentes = original.isin(["", "X", "x", "..", "..."])
    texto_numerico = texto_numerico.mask(ausentes, pd.NA)
    texto_numerico = texto_numerico.replace("-", "0")

    # Aceita ponto OU vírgula como separador decimal.
    # Não tenta adivinhar separadores de milhar.
    formato_valido = texto_numerico.str.fullmatch(
        r"[+-]?\d+(?:[.,]\d+)?",
        na=False,
    )

    df["valor_numerico"] = pd.to_numeric(
        texto_numerico.where(formato_valido)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    ).astype("Float64")

    invalidos = ~ausentes & ~formato_valido

    df.loc[invalidos, "situacao_valor"] = "formato_invalido"

    zeros_calculados = (
        df["valor_numerico"].eq(0).fillna(False)
        & original.ne("-")
        & ~invalidos
    )

    df.loc[
        zeros_calculados, "situacao_valor"
    ] = "zero_calculado_ou_arredondado"

    return df


# ============================================================
# 4. VALIDAÇÕES
# ============================================================

def validar_base(df, tabela, configuracao, relatorio):
    erros = []
    avisos = []

    # Ano
    anos = pd.to_numeric(df["ano"], errors="coerce")

    if not anos.eq(2022).all():
        erros.append("Existem anos ausentes, inválidos ou diferentes de 2022.")
    else:
        df["ano"] = anos.astype("Int64")

    if not df["ano_codigo"].eq("2022").all():
        erros.append("O código do ano não é 2022 em todas as linhas.")

    # Campos obrigatórios
    campos = [
        "nivel_territorial_codigo",
        "territorio_codigo",
        "territorio_nome",
        "variavel_codigo",
        "variavel",
        "unidade_codigo",
        "unidade",
    ]

    if tabela != "4714":
        campos += ["categoria_codigo", "categoria"]

    for coluna in campos:
        if df[coluna].isna().any() or df[coluna].eq("").any():
            erros.append(f"Campo obrigatório vazio: {coluna}")

    # Níveis e códigos territoriais
    nivel = df["nivel_territorial_codigo"]
    codigo = df["territorio_codigo"]

    if not nivel.isin(["1", "3", "6"]).all():
        erros.append("Foram encontrados níveis territoriais inesperados.")

    if not codigo.str.fullmatch(r"\d+", na=False).all():
        erros.append("Existem códigos territoriais não numéricos.")

    municipios = df[nivel.eq("6")]

    if not municipios["territorio_codigo"].str.fullmatch(
        r"23\d{5}", na=False
    ).all():
        erros.append(
            "Há código municipal fora do padrão de sete dígitos do Ceará."
        )

    if set(df.loc[nivel.eq("1"), "territorio_codigo"]) != {"1"}:
        erros.append("O registro territorial do Brasil está ausente ou inválido.")

    if set(df.loc[nivel.eq("3"), "territorio_codigo"]) != {"23"}:
        erros.append("O registro territorial do Ceará está ausente ou inválido.")

    quantidade_municipios = municipios["territorio_codigo"].nunique()

    if quantidade_municipios != 184:
        erros.append(
            f"Esperados 184 códigos municipais; encontrados "
            f"{quantidade_municipios}."
        )

    # Chave lógica
    chave = [
        "nivel_territorial_codigo",
        "territorio_codigo",
        "variavel_codigo",
        "ano",
    ]

    if tabela != "4714":
        chave.append("categoria_codigo")

    duplicatas_chave = int(df.duplicated(chave, keep=False).sum())

    if duplicatas_chave:
        erros.append(
            f"{duplicatas_chave} linhas possuem chave lógica repetida."
        )

    # Cardinalidade
    contagens = df.groupby(
        ["nivel_territorial_codigo", "territorio_codigo"]
    ).size()

    esperado = configuracao["registros_por_territorio"]
    contagens_incorretas = contagens[contagens.ne(esperado)]

    if not contagens_incorretas.empty:
        erros.append(
            f"{len(contagens_incorretas)} territórios não possuem "
            f"{esperado} registros."
        )

    if len(df) != configuracao["linhas_esperadas"]:
        erros.append(
            f"Quantidade de linhas inesperada: {len(df)}."
        )

    # Mesmas combinações de variável/categoria em cada território
    dimensoes = ["variavel_codigo"]

    if tabela != "4714":
        dimensoes.append("categoria_codigo")

    combinacoes = set(
        df[dimensoes].itertuples(index=False, name=None)
    )

    for territorio, grupo in df.groupby(
        ["nivel_territorial_codigo", "territorio_codigo"]
    ):
        encontradas = set(
            grupo[dimensoes].itertuples(index=False, name=None)
        )

        if encontradas != combinacoes:
            erros.append(
                f"Combinações de variável/categoria incompletas: {territorio}"
            )

    # Variáveis e unidades, conforme os arquivos fornecidos
    unidades_esperadas = (
        {"93": "45", "6318": "26", "614": "28"}
        if tabela == "4714"
        else {"381": "1020"}
    )

    if set(df["variavel_codigo"]) != set(unidades_esperadas):
        erros.append("As variáveis diferem das esperadas para esta extração.")

    unidade_esperada = df["variavel_codigo"].map(unidades_esperadas)

    if not df["unidade_codigo"].eq(unidade_esperada).all():
        erros.append("Unidade incompatível com a variável.")

    # Valores
    if df["situacao_valor"].eq("formato_invalido").any():
        erros.append("Existem valores com formato numérico não reconhecido.")

    if df["valor_numerico"].lt(0).fillna(False).any():
        erros.append("Existem valores negativos.")

    if tabela != "4714":
        fracionarios = df["valor_numerico"].dropna().mod(1).ne(0)

        if fracionarios.any():
            erros.append("Existem contagens de domicílios fracionárias.")

    ausentes = int(df["valor_numerico"].isna().sum())

    if ausentes:
        avisos.append(
            f"{ausentes} valores numéricos ausentes foram preservados."
        )

    relatorio.update({
        "linhas_processadas": len(df),
        "municipios_distintos": int(quantidade_municipios),
        "chave_logica": chave,
        "duplicatas_da_chave": duplicatas_chave,
        "valores_numericos_ausentes": ausentes,
        "percentual_ausente": round(
            100 * ausentes / len(df), 2
        ) if len(df) else 0,
        "situacoes_valores": {
            str(k): int(v)
            for k, v in df["situacao_valor"].value_counts().items()
        },
        "erros": erros,
        "avisos": avisos,
    })

    return df


def conferir_totais(df, tabela, relatorio):
    if tabela == "4714":
        relatorio["conferencia_totais"] = "Não se aplica."
        return

    partes = PARTES_DO_TOTAL.get(tabela)

    categorias = set(
        df.loc[df["categoria"].ne("Total"), "categoria_codigo"]
    )

    if partes is None or categorias != partes:
        relatorio["conferencia_totais"] = (
            "Pendente: confirmar categorias detalhadas e possíveis subtotais."
        )
        relatorio["avisos"].append(
            "Totais não somados automaticamente: falta confirmar "
            "que as categorias não se sobrepõem."
        )
        return

    divergencias = []
    incompletos = []

    chave = [
        "nivel_territorial_codigo",
        "territorio_codigo",
        "variavel_codigo",
        "ano",
    ]

    for territorio, grupo in df.groupby(chave):
        total = grupo.loc[
            grupo["categoria"].eq("Total"), "valor_numerico"
        ]

        detalhes = grupo.loc[
            grupo["categoria_codigo"].isin(partes), "valor_numerico"
        ]

        if (
            len(total) != 1
            or total.isna().any()
            or len(detalhes) != len(partes)
            or detalhes.isna().any()
        ):
            incompletos.append(str(territorio))
            continue

        if detalhes.sum() != total.iloc[0]:
            divergencias.append(str(territorio))

    relatorio["conferencia_totais"] = {
        "territorios_com_divergencia": divergencias,
        "territorios_sem_dados_completos": incompletos,
    }

    if divergencias:
        relatorio["erros"].append(
            f"Totais divergentes em {len(divergencias)} territórios."
        )


# ============================================================
# 5. PROCESSAMENTO E GRAVAÇÃO
# ============================================================

def processar_arquivo(caminho, tabela, configuracao):
    relatorio = {
        "tabela_sidra": tabela,
        "arquivo_origem": caminho.name,
        "sha256_origem": hashlib.sha256(
            caminho.read_bytes()
        ).hexdigest(),
    }

    df, encoding = carregar_csv(caminho)
    relatorio["encoding_leitura"] = encoding

    df = preparar_estrutura(df, tabela, relatorio)
    df = tratar_valores(df)
    df = validar_base(df, tabela, configuracao, relatorio)

    # Só confere totais se as verificações básicas passaram.
    if not relatorio["erros"]:
        conferir_totais(df, tabela, relatorio)

    # Catálogo: tudo que realmente aparece nos arquivos.
    for coluna in [
        "nivel_territorial", "variavel", "categoria", "unidade"
    ]:
        if coluna in df.columns:
            relatorio[coluna] = sorted(
                df[coluna].dropna().unique().tolist()
            )

    df["tabela_sidra"] = tabela
    df["arquivo_origem"] = caminho.name

    # Valores problemáticos ficam disponíveis para investigação.
    problemas = df[
        df["situacao_valor"].isin([
            "ausente",
            "valor_inibido",
            "nao_se_aplica",
            "nao_disponivel",
            "formato_invalido",
        ])
    ]

    problemas.to_csv(
        PASTA_RELATORIOS / f"{tabela}_valores_para_revisao.csv",
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )

    if relatorio["erros"]:
        relatorio["status"] = "BLOQUEADO"
        print(f"\nTabela {tabela}: NÃO foi salva em processed.")

        for erro in relatorio["erros"]:
            print(f"  ERRO: {erro}")

    else:
        ordem = [
            "nivel_territorial_codigo",
            "territorio_codigo",
            "variavel_codigo",
            "ano",
        ]

        if "categoria_codigo" in df.columns:
            ordem.append("categoria_codigo")

        df = df.sort_values(ordem).reset_index(drop=True)

        destino = PASTA_PROCESSED / configuracao["saida"]

        df.to_csv(
            destino,
            sep=";",
            index=False,
            encoding="utf-8-sig",
            na_rep="",
        )

        relatorio["status"] = (
            "SALVO_COM_AVISOS"
            if relatorio["avisos"]
            else "SALVO"
        )

        print(f"\nTabela {tabela}: salva em {destino}")
        print(f"  Linhas: {len(df)}")

    for aviso in relatorio["avisos"]:
        print(f"  AVISO: {aviso}")

    caminho_relatorio = PASTA_RELATORIOS / f"{tabela}_qualidade.json"

    with caminho_relatorio.open("w", encoding="utf-8") as arquivo:
        json.dump(
            relatorio,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    return relatorio["status"] != "BLOQUEADO"


def main():
    PASTA_PROCESSED.mkdir(parents=True, exist_ok=True)
    PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)

    falhou = False

    for tabela, configuracao in CONFIGURACOES.items():
        arquivos = sorted(
            PASTA_RAW.glob(configuracao["padrao"])
        )

        if len(arquivos) != 1:
            print(
                f"\nTabela {tabela}: esperado exatamente um arquivo; "
                f"encontrados {len(arquivos)}."
            )
            falhou = True
            continue

        try:
            sucesso = processar_arquivo(
                arquivos[0], tabela, configuracao
            )
            falhou = falhou or not sucesso

        except (ValueError, OSError, pd.errors.ParserError) as erro:
            print(f"\nFalha na tabela {tabela}: {erro}")
            falhou = True

    if falhou:
        print(
            "\nProcessamento incompleto. Confira os erros. "
            "Arquivos processed de execuções anteriores não foram apagados."
        )
        raise SystemExit(1)

    print("\nProcessamento concluído. Confira os avisos e relatórios.")


if __name__ == "__main__":
    main()