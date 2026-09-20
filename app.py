import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
from pathlib import Path

st.set_page_config(page_title="Saneamento no Ceará — 2022", layout="wide")

# Todos os caminhos partem da pasta onde este app.py está localizado. Assim, o
# aplicativo funciona mesmo quando o comando é executado a partir de outra pasta.
RAIZ_PROJETO = Path(__file__).resolve().parent
PASTA_DADOS = RAIZ_PROJETO / "dados" / "raw"
PASTA_DADOS_ORIGINAIS = PASTA_DADOS / "dados_originais"
PASTA_DADOS_COMUNS = PASTA_DADOS / "dados_comuns"

CAMINHOS = {
    "agua": PASTA_DADOS_ORIGINAIS / "t6803_abastecimento_agua_2022_ce_br.csv",
    "esgoto": PASTA_DADOS_ORIGINAIS / "t6805_esgotamento_sanitario_2022_ce_br.csv",
    "lixo": PASTA_DADOS_ORIGINAIS / "t6892_destino_lixo_2022_ce_br.csv",
    "pop": PASTA_DADOS_ORIGINAIS / "t4714_populacao_area_densidade_2022_ce_br.csv",
    "malha": PASTA_DADOS_COMUNS / "malha_municipal_ce_2022.geojson",
}


def validar_caminhos():
    """Interrompe a execução com uma mensagem clara se algum dado estiver ausente."""
    ausentes = [f"{nome}: {caminho}" for nome, caminho in CAMINHOS.items() if not caminho.is_file()]
    if ausentes:
        detalhes = "\n".join(f"- {item}" for item in ausentes)
        raise FileNotFoundError(
            "Arquivos necessários para o aplicativo não foram encontrados:\n"
            f"{detalhes}\nRaiz do projeto utilizada: {RAIZ_PROJETO}"
        )


validar_caminhos()


@st.cache_data
def ler_tabela(path):
    df = pd.read_csv(
        path,
        sep=";",
        dtype=str,
        keep_default_na=False,
        skiprows=[1],
        encoding="utf-8-sig",
    )
    # Na convenção destes arquivos SIDRA, "-" significa zero absoluto.
    df = df.replace({"-": "0", "": pd.NA})
    df["V"] = pd.to_numeric(df["V"], errors="coerce")
    df["D1C"] = df["D1C"].astype(str).str.zfill(7)
    return df.query("NC == '6'").copy()


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

    base["pct_agua_sem_rede"] = 100 * base["agua_sem_rede"].fillna(0) / base["agua_total"]
    base["pct_esgoto_rede"] = 100 * base["esg_rede"].fillna(0) / base["esg_total"]
    base["pct_esgoto_inadequado"] = 100 * (
        base[["esg_rudimentar", "esg_vala", "esg_rio", "esg_sem_ban"]].fillna(0).sum(axis=1)
    ) / base["esg_total"]
    base["pct_lixo_inadequado"] = 100 * (
        base[["lixo_queimado", "lixo_enterrado", "lixo_terreno_baldio"]].fillna(0).sum(axis=1)
    ) / base["lixo_total"]

    base["indice_deficit"] = (
        base["pct_agua_sem_rede"] + base["pct_esgoto_inadequado"] + base["pct_lixo_inadequado"]
    ) / 3

    return base, relatorio_join


base, relatorio = montar_base()

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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Municípios analisados", len(base))
c2.metric("Água sem rede geral", f"{100 * base['agua_sem_rede'].sum() / base['agua_total'].sum():.1f}%")
c3.metric(
    "Esgoto inadequado",
    f"{100 * base[['esg_rudimentar', 'esg_vala', 'esg_rio', 'esg_sem_ban']].fillna(0).sum().sum() / base['esg_total'].sum():.1f}%",
)
c4.metric(
    "Lixo mal destinado",
    f"{100 * base[['lixo_queimado', 'lixo_enterrado', 'lixo_terreno_baldio']].fillna(0).sum().sum() / base['lixo_total'].sum():.1f}%",
)

st.divider()

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

st.header("Comparação territorial")


@st.cache_data
def carregar_malha():
    malha = gpd.read_file(CAMINHOS["malha"])
    malha["codarea"] = malha["codarea"].astype(str)
    malha["geometry"] = malha.geometry.make_valid()
    return malha


malha = carregar_malha()

mapa_df = filtrado.rename(columns={"D1C": "codarea"})
lon_min, lat_min, lon_max, lat_max = malha.total_bounds
fig_mapa = px.choropleth_map(
    mapa_df,
    geojson=malha.__geo_interface__,
    locations="codarea",
    featureidkey="properties.codarea",
    color="indice_deficit",
    color_continuous_scale="Reds",
    hover_name="municipio",
    labels={"indice_deficit": "Índice de déficit"},
    map_style="carto-positron",
    center={"lat": (lat_min + lat_max) / 2, "lon": (lon_min + lon_max) / 2},
    zoom=6,
    opacity=0.7,
)
fig_mapa.update_layout(margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig_mapa, width="stretch")
st.caption(
    "Leitura visual do padrão territorial (não é clusterização automática — "
    "o projeto não permite aprendizado de máquina). Observem se os piores "
    "índices se concentram em alguma região do estado ou aparecem espalhados."
)

st.divider()

st.header("Municípios prioritários (maior déficit combinado)")
top_piores = filtrado.sort_values("indice_deficit", ascending=False).head(15)
fig_rank = px.bar(
    top_piores, x="indice_deficit", y="municipio", orientation="h",
    color="indice_deficit", color_continuous_scale="Reds",
    labels={"indice_deficit": "Índice de déficit (0-100)", "municipio": ""},
)
fig_rank.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=500)
st.plotly_chart(fig_rank, width="stretch")
st.caption(
    "Índice exploratório da equipe: média simples de % água sem rede, "
    "% esgoto inadequado e % lixo mal destinado. Não é um indicador oficial do IBGE."
)

st.divider()

st.header("Cruzamento entre bases")


@st.cache_data
def calcular_distancia_fortaleza():
    malha_proj = carregar_malha().to_crs(epsg=3857)
    malha_proj["centroide"] = malha_proj.geometry.centroid
    fort = malha_proj.loc[malha_proj["codarea"] == "2304400", "centroide"].iloc[0]
    malha_proj["dist_fortaleza_km"] = malha_proj["centroide"].distance(fort) / 1000
    return malha_proj[["codarea", "dist_fortaleza_km"]].rename(columns={"codarea": "D1C"})


filtrado = filtrado.merge(calcular_distancia_fortaleza(), on="D1C", how="left")

tab1, tab2, tab3, tab4 = st.tabs([
    "Água x esgoto (descompasso)",
    "Densidade x cobertura de esgoto",
    "Distância até Fortaleza",
    "Lixo x densidade (quartis)",
])

with tab1:
    filtrado["gap_agua_esgoto"] = filtrado["pct_esgoto_inadequado"] - filtrado["pct_agua_sem_rede"]
    top_gap = filtrado.sort_values("gap_agua_esgoto", ascending=False).head(15)
    fig_gap = px.bar(
        top_gap, x="gap_agua_esgoto", y="municipio", orientation="h",
        color="gap_agua_esgoto", color_continuous_scale="Reds",
        labels={"gap_agua_esgoto": "Gap esgoto - água (p.p.)", "municipio": ""},
    )
    fig_gap.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=500)
    st.plotly_chart(fig_gap, width="stretch")
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
    st.plotly_chart(fig_dens, width="stretch")
    st.caption("Cada ponto é um município do recorte filtrado.")

with tab3:
    fig_dist = px.scatter(
        filtrado, x="dist_fortaleza_km", y="pct_esgoto_rede", hover_name="municipio",
        labels={"dist_fortaleza_km": "Distância até Fortaleza (km, centroide)", "pct_esgoto_rede": "% esgoto rede geral"},
    )
    st.plotly_chart(fig_dist, width="stretch")
    corr = filtrado["dist_fortaleza_km"].corr(filtrado["pct_esgoto_rede"])
    st.info(
        f"Correlação no recorte atual: **{corr:.2f}**. Proximidade geográfica "
        "com a capital não garante, sozinha, melhor cobertura de esgoto."
    )

with tab4:
    filtrado["dens_quartil"] = pd.qcut(filtrado["densidade"], min(4, filtrado["densidade"].nunique()), duplicates="drop")
    medias = filtrado.groupby("dens_quartil", observed=True)["pct_lixo_inadequado"].mean().reset_index()
    medias["dens_quartil"] = medias["dens_quartil"].astype(str)
    fig_lixo_dens = px.bar(
        medias, x="dens_quartil", y="pct_lixo_inadequado",
        labels={"dens_quartil": "Quartil de densidade (hab/km²)", "pct_lixo_inadequado": "% lixo inadequado (média)"},
    )
    st.plotly_chart(fig_lixo_dens, width="stretch")
    st.caption("Municípios menos densos tendem a queimar/enterrar/jogar mais lixo, por falta de coleta regular.")

st.divider()

with st.expander("Revisão: as 8 categorias de esgotamento sanitário"):
    cats_map = {
        "Rede geral ou pluvial": "esg_rede",
        "Fossa séptica ligada": "esg_fossa_lig",
        "Fossa séptica não ligada": "esg_fossa_nlig",
        "Fossa rudimentar/buraco": "esg_rudimentar",
        "Vala": "esg_vala",
        "Rio/lago/córrego/mar": "esg_rio",
        "Outra forma": "esg_outra",
        "Sem banheiro": "esg_sem_ban",
    }
    soma = {k: filtrado[v].sum() for k, v in cats_map.items()}
    total = sum(soma.values())
    df_cats = pd.DataFrame({
        "categoria": list(soma.keys()),
        "pct": [100 * v / total for v in soma.values()],
    }).sort_values("pct")
    fig_cats = px.bar(
        df_cats, x="pct", y="categoria", orientation="h",
        labels={"pct": "% dos domicílios (recorte atual)", "categoria": ""},
    )
    st.plotly_chart(fig_cats, width="stretch")
    st.warning(
        "Hoje o indicador `pct_esgoto_inadequado` usa só 4 das 8 categorias "
        "(rudimentar, vala, rio, sem banheiro). **Fossa séptica não ligada** "
        "e **outra forma** ainda não têm classificação definida pela equipe — "
        "decidir isso antes da entrega final."
    )

st.divider()

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
- A distância até Fortaleza é calculada entre centroides (projeção
  métrica aproximada, EPSG:3857) — serve para comparação relativa entre
  municípios, não para medições cartográficas de precisão.
- "Fossa séptica não ligada à rede" e "outra forma" (juntas, ~21% dos
  domicílios do estado) ainda não têm classificação definida como
  adequado/inadequado — ver a seção "Revisão: as 8 categorias de
  esgotamento sanitário" acima.
        """
    )
