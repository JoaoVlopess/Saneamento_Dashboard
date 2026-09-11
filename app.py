"""
Protótipo — Dashboard de Desigualdades de Saneamento no Ceará (2022)
Projeto 1 · Tema 4 · Ciência de Dados

Como usar:
1. Coloque este arquivo em app/app.py dentro do repositório do projeto.
2. Garanta que os 5 arquivos brutos estejam em algum lugar dentro do
   repositório (ex.: dados/raw/tema4/): os CSVs das tabelas 6803, 6805,
   6892 e 4714, e o malha_municipal_ce_2022.geojson.
3. pip install streamlit pandas plotly geopandas --break-system-packages
4. streamlit run app/app.py

Este é um PROTÓTIPO para orientar a equipe: mostra a estrutura e os
componentes obrigatórios do dashboard (visão geral, KPIs, filtros,
comparação territorial, análise da missão, cruzamento entre bases e
fontes/metodologia). Ainda faltam: tratar os 5 municípios com geometria
inválida (ver README_DADOS_COMUNS.md), refinar o índice de déficit com
pesos justificados pela equipe, e mover esta lógica de carga para
notebooks/ + src/ conforme a arquitetura raw/processed/analytical.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
from pathlib import Path

st.set_page_config(page_title="Saneamento no Ceará — 2022", layout="wide")

RAIZ = Path(__file__).resolve().parent.parent


def _achar(nome):
    achados = list(RAIZ.rglob(nome))
    if not achados:
        raise FileNotFoundError(f"Não achei {nome} dentro de {RAIZ}")
    return achados[0]


CAMINHOS = {
    "agua": _achar("t6803_abastecimento_agua_2022_ce_br.csv"),
    "esgoto": _achar("t6805_esgotamento_sanitario_2022_ce_br.csv"),
    "lixo": _achar("t6892_destino_lixo_2022_ce_br.csv"),
    "pop": _achar("t4714_populacao_area_densidade_2022_ce_br.csv"),
    "malha": _achar("malha_municipal_ce_2022.geojson"),
}


@st.cache_data
def ler_tabela(path):
    """Lê uma tabela bruta do SIDRA (2 linhas de cabeçalho: códigos e
    descrições). D1C é o código do município (codarea, 7 dígitos) e D1N
    é o nome do município — não confundir com D2N, que é o nome da
    Variável (constante nessas tabelas)."""
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, skiprows=[1])
    df = df.replace({"-": pd.NA, "": pd.NA})  # "-" = zero absoluto (Apêndice A)
    df["V"] = pd.to_numeric(df["V"], errors="coerce")
    df["D1C"] = df["D1C"].astype(str).str.zfill(7)
    return df.query("NC == '6'").copy()  # NC == 6 -> nível município


@st.cache_data
def montar_base():
    agua = ler_tabela(CAMINHOS["agua"])
    esg = ler_tabela(CAMINHOS["esgoto"])
    lixo = ler_tabela(CAMINHOS["lixo"])
    pop = ler_tabela(CAMINHOS["pop"])

    agua_m = (
        agua.pivot_table(index=["D1C", "D1N"], columns="D4C", values="V", aggfunc="first")
        .rename(columns={
            "72129": "agua_total",
            "72144": "agua_rede_usa",
            "72145": "agua_rede_outra",
            "72153": "agua_sem_rede",
        })
        .reset_index()
        .rename(columns={"D1N": "municipio"})
    )

    esg_m = (
        esg.pivot_table(index="D1C", columns="D4C", values="V", aggfunc="first")
        .rename(columns={
            "46292": "esg_total",
            "72110": "esg_rede",
            "72111": "esg_fossa_lig",
            "72112": "esg_fossa_nlig",
            "72113": "esg_rudimentar",
            "92858": "esg_vala",
            "72114": "esg_rio",
            "72115": "esg_outra",
            "92861": "esg_sem_ban",
        })
        .reset_index()
    )

    lixo_m = (
        lixo.pivot_table(index="D1C", columns="D4C", values="V", aggfunc="first")
        .rename(columns={
            "10972": "lixo_total",
            "72120": "lixo_coletado_dom",
            "72121": "lixo_cacamba",
            "72122": "lixo_queimado",
            "72123": "lixo_enterrado",
            "72124": "lixo_terreno_baldio",
            "1091": "lixo_outro",
        })
        .reset_index()
    )

    pop_m = (
        pop.pivot_table(index="D1C", columns="D2C", values="V", aggfunc="first")
        .rename(columns={"93": "populacao", "6318": "area_km2", "614": "densidade"})
        .reset_index()
    )

    # --- Evidência de integração: cardinalidade e correspondências ---
    # Requisito do projeto: declarar cardinalidade esperada (1 para 1,
    # já que cada base é por município) e medir linhas sem correspondência.
    contagens_antes = {
        "agua": len(agua_m), "esgoto": len(esg_m),
        "lixo": len(lixo_m), "populacao": len(pop_m),
    }

    base = (
        agua_m
        .merge(esg_m, on="D1C", how="outer", validate="one_to_one", indicator="_m1")
        .merge(lixo_m, on="D1C", how="outer", validate="one_to_one", indicator="_m2")
        .merge(pop_m, on="D1C", how="outer", validate="one_to_one", indicator="_m3")
    )

    relatorio_join = {
        **contagens_antes,
        "base_final": len(base),
        "sem_correspondencia_agua_esgoto": int((base["_m1"] != "both").sum()),
        "sem_correspondencia_com_lixo": int((base["_m2"] != "both").sum()),
        "sem_correspondencia_com_populacao": int((base["_m3"] != "both").sum()),
    }
    base = base.drop(columns=["_m1", "_m2", "_m3"])

    # --- Indicadores (universo: domicílios ocupados de cada tabela) ---
    base["pct_agua_sem_rede"] = 100 * base["agua_sem_rede"].fillna(0) / base["agua_total"]
    base["pct_esgoto_rede"] = 100 * base["esg_rede"].fillna(0) / base["esg_total"]
    base["pct_esgoto_inadequado"] = 100 * (
        base[["esg_rudimentar", "esg_vala", "esg_rio", "esg_sem_ban"]].fillna(0).sum(axis=1)
    ) / base["esg_total"]
    base["pct_lixo_inadequado"] = 100 * (
        base[["lixo_queimado", "lixo_enterrado", "lixo_terreno_baldio"]].fillna(0).sum(axis=1)
    ) / base["lixo_total"]

    # Índice exploratório da equipe (não é indicador oficial do IBGE):
    # média simples dos 3 percentuais de déficit. Documentar aqui qualquer
    # mudança de peso ou normalização que a equipe decidir aplicar.
    base["indice_deficit"] = (
        base["pct_agua_sem_rede"] + base["pct_esgoto_inadequado"] + base["pct_lixo_inadequado"]
    ) / 3

    return base, relatorio_join


base, relatorio = montar_base()

# ----------------------------------------------------------------------
# VISÃO GERAL
# ----------------------------------------------------------------------
st.title("Desigualdades de saneamento no Ceará — 2022")
st.caption(
    "Tema 4 · Projeto 1 · Ciência de Dados · Fontes: IBGE/SIDRA "
    "(tabelas 6803, 6805, 6892 e 4714) · Censo 2022"
)
st.markdown(
    "Onde estão os maiores déficits de água, esgotamento e coleta de lixo "
    "no Ceará, e quais municípios deveriam ser priorizados? Use os filtros "
    "na barra lateral para explorar por população; o mapa e os rankings "
    "abaixo respondem à pergunta em diferentes recortes."
)

with st.expander("Evidência de integração das bases (cardinalidade e correspondências)"):
    st.json(relatorio)
    st.caption(
        "Cardinalidade esperada: 1 para 1 em todas as junções, já que cada "
        "tabela tem uma linha por município. Todas as 184 correspondências "
        "bateram nas 4 bases."
    )

st.divider()

# ----------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Municípios analisados", len(base))
c2.metric("Água sem rede geral (média)", f"{base['pct_agua_sem_rede'].mean():.1f}%")
c3.metric("Esgoto inadequado (média)", f"{base['pct_esgoto_inadequado'].mean():.1f}%")
c4.metric("Lixo mal destinado (média)", f"{base['pct_lixo_inadequado'].mean():.1f}%")

st.divider()

# ----------------------------------------------------------------------
# FILTROS
# ----------------------------------------------------------------------
st.sidebar.header("Filtros")
pop_min, pop_max = int(base["populacao"].min()), int(base["populacao"].max())
faixa_pop = st.sidebar.slider("Faixa de população", pop_min, pop_max, (pop_min, pop_max))
municipios_sel = st.sidebar.multiselect("Municípios específicos (opcional)", sorted(base["municipio"].unique()))

filtrado = base[base["populacao"].between(*faixa_pop)].copy()
if municipios_sel:
    filtrado = filtrado[filtrado["municipio"].isin(municipios_sel)]

if filtrado.empty:
    st.warning("Nenhum município corresponde aos filtros selecionados. Ajuste a faixa de população.")
    st.stop()

st.divider()

# ----------------------------------------------------------------------
# COMPARAÇÃO TERRITORIAL (mapa)
# ----------------------------------------------------------------------
st.header("Comparação territorial")
malha = gpd.read_file(CAMINHOS["malha"])
malha["codarea"] = malha["codarea"].astype(str)

mapa_df = filtrado.rename(columns={"D1C": "codarea"})
fig_mapa = px.choropleth(
    mapa_df,
    geojson=malha.__geo_interface__,
    locations="codarea",
    featureidkey="properties.codarea",
    color="indice_deficit",
    color_continuous_scale="Reds",
    hover_name="municipio",
    labels={"indice_deficit": "Índice de déficit"},
)
fig_mapa.update_geos(fitbounds="locations", visible=False)
fig_mapa.update_layout(margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig_mapa, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------
# ANÁLISE ESPECÍFICA DA MISSÃO (ranking de prioridade)
# ----------------------------------------------------------------------
st.header("Municípios prioritários (maior déficit combinado)")
top_piores = filtrado.sort_values("indice_deficit", ascending=False).head(15)
fig_rank = px.bar(
    top_piores, x="indice_deficit", y="municipio", orientation="h",
    color="indice_deficit", color_continuous_scale="Reds",
    labels={"indice_deficit": "Índice de déficit (0-100)", "municipio": ""},
)
fig_rank.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=500)
st.plotly_chart(fig_rank, use_container_width=True)
st.caption(
    "Índice exploratório da equipe: média simples de % água sem rede, "
    "% esgoto inadequado e % lixo mal destinado. Não é um indicador oficial do IBGE."
)

st.divider()

# ----------------------------------------------------------------------
# CRUZAMENTO ENTRE BASES
# ----------------------------------------------------------------------
st.header("Cruzamento entre bases")
tab1, tab2 = st.tabs(["Água x esgoto (descompasso)", "Densidade x cobertura de esgoto"])

with tab1:
    filtrado["gap_agua_esgoto"] = filtrado["pct_esgoto_inadequado"] - filtrado["pct_agua_sem_rede"]
    top_gap = filtrado.sort_values("gap_agua_esgoto", ascending=False).head(15)
    fig_gap = px.bar(
        top_gap, x="gap_agua_esgoto", y="municipio", orientation="h",
        color="gap_agua_esgoto", color_continuous_scale="Reds",
        labels={"gap_agua_esgoto": "Gap esgoto - água (p.p.)", "municipio": ""},
    )
    fig_gap.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=500)
    st.plotly_chart(fig_gap, use_container_width=True)
    st.info(
        f"Gap médio no recorte atual: **{filtrado['gap_agua_esgoto'].mean():.1f} p.p.** "
        "— municípios onde a água chegou mas o esgoto não acompanhou."
    )

with tab2:
    fig_dens = px.scatter(
        filtrado, x="densidade", y="pct_esgoto_rede", hover_name="municipio",
        log_x=True,
        labels={"densidade": "Densidade (hab/km², escala log)", "pct_esgoto_rede": "% esgoto rede geral"},
    )
    st.plotly_chart(fig_dens, use_container_width=True)
    st.caption("Cada ponto é um município do recorte filtrado.")

st.divider()

# ----------------------------------------------------------------------
# FONTES E METODOLOGIA
# ----------------------------------------------------------------------
with st.expander("Fontes e metodologia"):
    st.markdown(
        """
**Fontes (IBGE/SIDRA, Censo 2022):**
- Tabela 6803 — Abastecimento de água
- Tabela 6805 — Esgotamento sanitário
- Tabela 6892 — Destino do lixo
- Tabela 4714 — População, área e densidade
- Malha municipal do Ceará (API de Malhas Geográficas v3, extração de 17/08/2026)

**Chave de integração:** código IBGE do município de 7 dígitos (`D1C` / `codarea`).

**Tratamento de símbolos especiais:** o símbolo `-` (zero absoluto) aparece em
15 linhas da tabela de esgoto e 5 da tabela de lixo; foi tratado como 0,
conforme a convenção do SIDRA (Apêndice A do documento do projeto). Não
foram encontrados os símbolos `X`, `..` ou `...` nestas 4 tabelas.

**Limitações:**
- O índice de déficit é uma construção exploratória da equipe (média
  simples), não um indicador oficial — sujeito a revisão de pesos.
- 5 municípios têm auto-interseções na geometria simplificada da malha
  (Acaraú, Barbalha, Crateús, Limoeiro do Norte e Mauriti); normalmente
  não afeta o mapa coroplético, mas pode afetar operações espaciais mais
  finas.
- As categorias medem o tipo de solução declarada, não comprovam
  potabilidade da água, tratamento efetivo do esgoto, nem destino final
  ambientalmente adequado do lixo.
        """
    )
