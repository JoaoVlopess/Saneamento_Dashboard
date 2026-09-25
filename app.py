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

Organização final das análises:
  1. Revisão metodológica — categorias de água, esgoto e lixo (3 abas)
  2. KPIs gerais
  3. Comparação territorial e municípios prioritários
  4. Cruzamentos entre bases (empilhados, um por seção):
     a) Concentração por km² + lixo e densidade (abas)
     b) Água x esgoto
     c) Distância até Fortaleza + até os melhores têm esgoto ruim (abas)
     d) Correlação entre dimensões

Pendências conhecidas: mover esta lógica de carga para notebooks/ + src/
conforme a arquitetura raw/processed/analytical, e a equipe decidir a
classificação de "fossa séptica não ligada" e "outra forma" (Insight 6).
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
    df = df.replace({"-": pd.NA, "": pd.NA})
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

    base["domicilios_deficit_esgoto"] = base[
        ["esg_rudimentar", "esg_vala", "esg_rio", "esg_sem_ban"]
    ].fillna(0).sum(axis=1)
    base["deficit_esgoto_por_km2"] = base["domicilios_deficit_esgoto"] / base["area_km2"]

    N_DESTAQUE = 10
    piores_idx = base.nlargest(N_DESTAQUE, "indice_deficit").index
    melhores_idx = base.nsmallest(N_DESTAQUE, "indice_deficit").index

    media_deficit = base["indice_deficit"].mean()
    base["dist_media"] = (base["indice_deficit"] - media_deficit).abs()
    restantes = base.index.difference(piores_idx.union(melhores_idx))
    proximos_idx = base.loc[restantes].nsmallest(N_DESTAQUE, "dist_media").index

    base["categoria_desempenho"] = "Demais municípios"
    base.loc[melhores_idx, "categoria_desempenho"] = "Entre os 10 melhores"
    base.loc[piores_idx, "categoria_desempenho"] = "Entre os 10 piores"
    base.loc[proximos_idx, "categoria_desempenho"] = "Próximo da média estadual"

    return base, relatorio_join


base, relatorio = montar_base()

CORES_DESEMPENHO = {
    "Entre os 10 melhores": "#1baf7a",
    "Próximo da média estadual": "#e0b400",
    "Entre os 10 piores": "#c0392b",
    "Demais municípios": "#b5b5b5",
}

st.title("Desigualdades de saneamento no Ceará — 2022")
st.caption(
    "Tema 4 · Projeto 1 · Ciência de Dados · Fontes: IBGE/SIDRA "
    "(tabelas 6803, 6805, 6892 e 4714) · Censo 2022"
)
st.markdown(
    "Onde estão os maiores déficits de água, esgotamento e coleta de lixo "
    "no Ceará, e quais municípios deveriam ser priorizados? Este protótipo "
    "organiza a resposta em análises detalhadas ao longo da página. "
    "Use o filtro na barra lateral para explorar por município específico."
)

with st.expander("Evidência de integração das bases (cardinalidade e correspondências)"):
    st.json(relatorio)
    st.caption(
        "Cardinalidade esperada: 1 para 1 em todas as junções, já que cada "
        "tabela tem uma linha por município. Todas as 184 correspondências "
        "bateram nas 4 bases."
    )

st.divider()

# ---------------------------------------------------------------------------
# Filtros (barra lateral) — movidos para antes da revisão metodológica,
# que já usa o recorte `filtrado`
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")
municipios_sel = st.sidebar.multiselect(
    "Municípios específicos (opcional)", sorted(base["municipio"].unique())
)

filtrado = base.copy()
if municipios_sel:
    filtrado = filtrado[filtrado["municipio"].isin(municipios_sel)]

if filtrado.empty:
    st.warning("Nenhum município corresponde à seleção. Ajuste os municípios escolhidos.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Revisão metodológica (agora antes dos KPIs)
# ---------------------------------------------------------------------------
st.header("🧭 Revisão metodológica")
st.markdown("#### 🔎 Categorias consideradas nas três dimensões")

tab_agua_cat, tab_esgoto_cat, tab_lixo_cat = st.tabs(["Água", "Esgoto", "Lixo"])


def mostrar_categorias(categorias, titulo_eixo):
    soma = {k: filtrado[v].fillna(0).sum() for k, v in categorias.items()}
    total = sum(soma.values())
    if total == 0:
        st.warning("Não há dados suficientes para exibir esta distribuição.")
        return
    df_cat = pd.DataFrame({
        "categoria": list(soma.keys()),
        "pct": [round(100 * v / total, 2) for v in soma.values()],
    }).sort_values("pct")
    fig = px.bar(
        df_cat, x="pct", y="categoria", orientation="h",
        labels={"pct": "% dos domicílios (recorte atual)", "categoria": ""},
    )
    fig.update_traces(texttemplate="%{x:.2f}%", textposition="outside")
    fig.update_layout(height=max(350, 55 * len(df_cat)))
    st.plotly_chart(fig, width="stretch")


with tab_agua_cat:
    mostrar_categorias({
        "Rede geral": "agua_rede_usa",
        "Outra forma de abastecimento por rede": "agua_rede_outra",
        "Sem rede geral": "agua_sem_rede",
    }, "Água")
    st.caption(
        "Distribuição das categorias de abastecimento de água utilizadas "
        "no cálculo do indicador."
    )

with tab_esgoto_cat:
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
    mostrar_categorias(cats_map, "Esgoto")
    st.caption(
        "Classificação atual da equipe: as categorias 'Fossa séptica não ligada' "
        "e 'Outra forma' permanecem indefinidas e não entram em "
        "pct_esgoto_inadequado."
    )

with tab_lixo_cat:
    mostrar_categorias({
        "Coletado": "lixo_coletado_dom",
        "Caçamba": "lixo_cacamba",
        "Queimado": "lixo_queimado",
        "Enterrado": "lixo_enterrado",
        "Terreno baldio": "lixo_terreno_baldio",
        "Outro destino": "lixo_outro",
    }, "Lixo")
    st.caption(
        "A classificação de 'lixo inadequado' usada no índice considera "
        "queimado, enterrado e terreno baldio."
    )

st.divider()

# ---------------------------------------------------------------------------
# KPIs gerais
# ---------------------------------------------------------------------------
st.header("📊 KPIs gerais")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Municípios analisados", len(base))
c2.metric(
    "Água sem rede geral (média entre municípios)",
    f"{base['pct_agua_sem_rede'].mean():.2f}%",
)
c3.metric(
    "Esgoto inadequado (média entre municípios)",
    f"{base['pct_esgoto_inadequado'].mean():.2f}%",
)
c4.metric(
    "Lixo mal destinado (média entre municípios)",
    f"{base['pct_lixo_inadequado'].mean():.2f}%",
)

fig_comparacao = px.bar(
    pd.DataFrame({
        "dimensao": ["Água sem rede", "Esgoto sem rede geral", "Lixo inadequado"],
        "pct": [
            base["pct_agua_sem_rede"].mean(),
            100 - base["pct_esgoto_rede"].mean(),
            base["pct_lixo_inadequado"].mean(),
        ],
    }),
    x="dimensao", y="pct", color="dimensao",
    color_discrete_sequence=["#2a78d6", "#c0392b", "#e08e00"],
    labels={"pct": "% médio dos domicílios", "dimensao": ""},
)
fig_comparacao.update_layout(showlegend=False, height=380)
fig_comparacao.update_traces(texttemplate="%{y:.2f}%", textposition="outside")
st.plotly_chart(fig_comparacao, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# Comparação territorial
# ---------------------------------------------------------------------------
st.header("🗺️ Comparação territorial")
st.markdown("#### 🔎 Padrão geográfico do déficit, por dimensão")


@st.cache_data
def carregar_malha():
    malha = gpd.read_file(CAMINHOS["malha"])
    malha["codarea"] = malha["codarea"].astype(str)
    malha["geometry"] = malha.geometry.make_valid()
    return malha


malha = carregar_malha()

mapa_df = filtrado.rename(columns={"D1C": "codarea"})
lon_min, lat_min, lon_max, lat_max = malha.total_bounds

tab_indice, tab_agua, tab_esg, tab_lixo = st.tabs([
    "Índice combinado", "Água", "Esgoto", "Lixo",
])
mapas_territorio = {
    tab_indice: ("indice_deficit", "Índice de déficit"),
    tab_agua: ("pct_agua_sem_rede", "% sem rede geral"),
    tab_esg: ("pct_esgoto_inadequado", "% esgoto inadequado"),
    tab_lixo: ("pct_lixo_inadequado", "% lixo mal destinado"),
}
for tab, (coluna, rotulo) in mapas_territorio.items():
    with tab:
        fig_terr = px.choropleth_map(
            mapa_df,
            geojson=malha.__geo_interface__,
            locations="codarea",
            featureidkey="properties.codarea",
            color=coluna,
            color_continuous_scale="Reds",
            hover_name="municipio",
            labels={coluna: rotulo},
            map_style="carto-positron",
            center={"lat": (lat_min + lat_max) / 2, "lon": (lon_min + lon_max) / 2},
            zoom=6,
            opacity=0.7,
        )
        fig_terr.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_terr, width="stretch")
        if coluna == "indice_deficit":
            st.info(
                "Leitura **visual e descritiva** do padrão territorial"
            )
        else:
            st.caption(
                "Escala de cor relativa a esta variável — não é comparável "
                "diretamente com as outras abas."
            )

st.divider()

# ---------------------------------------------------------------------------
# Municípios prioritários
# ---------------------------------------------------------------------------
st.header("🎯 Municípios prioritários (maior déficit combinado)")
top_piores = filtrado.sort_values("indice_deficit", ascending=False).head(15)
fig_rank = px.bar(
    top_piores, x="indice_deficit", y="municipio", orientation="h",
    color="indice_deficit", color_continuous_scale="Reds",
    labels={"indice_deficit": "Índice de déficit (0-100)", "municipio": ""},
)
fig_rank.update_layout(yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=500)
fig_rank.update_traces(texttemplate="%{x:.2f}", textposition="outside")
st.plotly_chart(fig_rank, width="stretch")
st.caption(
    "Índice exploratório da equipe: média simples de % água sem rede, "
    "% esgoto inadequado e % lixo mal destinado. Não é um indicador oficial do IBGE."
)

st.divider()

# ---------------------------------------------------------------------------
# Cruzamentos entre bases (empilhados, um por seção)
# ---------------------------------------------------------------------------
st.header("🔗 Cruzamentos entre bases")


@st.cache_data
def calcular_distancia_fortaleza():
    """Distância do centroide de cada município até o centroide de
    Fortaleza, usando só a malha geográfica (sem fonte externa)."""
    malha_proj = carregar_malha().to_crs(epsg=3857)
    malha_proj["centroide"] = malha_proj.geometry.centroid
    fort = malha_proj.loc[malha_proj["codarea"] == "2304400", "centroide"].iloc[0]
    malha_proj["dist_fortaleza_km"] = malha_proj["centroide"].distance(fort) / 1000
    return malha_proj[["codarea", "dist_fortaleza_km"]].rename(columns={"codarea": "D1C"})


filtrado = filtrado.merge(calcular_distancia_fortaleza(), on="D1C", how="left")

# --- 1) Concentração por km² + Lixo e densidade (área com abas) -------------
st.subheader("📐 Concentração de déficit de esgoto e lixo por densidade")

tab_conc, tab_lixo_dens = st.tabs([
    "Concentração por km²",
    "Lixo e densidade",
])

with tab_conc:
    st.markdown("#### Concentração de déficit de esgoto por km²")

    top_concentracao = filtrado.nlargest(10, "deficit_esgoto_por_km2")

    fig_concentracao = px.bar(
        top_concentracao,
        x="deficit_esgoto_por_km2",
        y="municipio",
        orientation="h",
        color="deficit_esgoto_por_km2",
        color_continuous_scale="Reds",
        labels={
            "deficit_esgoto_por_km2": "Domicílios em déficit por km²",
            "municipio": ""
        },
    )

    fig_concentracao.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis=dict(tickformat=".2f"),
        coloraxis_showscale=False,
        height=450
    )

    fig_concentracao.update_traces(
        texttemplate="%{x:.2f}",
        textposition="outside",
        hovertemplate=(
            "%{y}<br>"
            "Domicílios em déficit por km²: %{x:.2f}"
            "<extra></extra>"
        )
    )

    st.plotly_chart(fig_concentracao, width="stretch")

    fortaleza_row = filtrado[filtrado["municipio"] == "Fortaleza"]

    if not fortaleza_row.empty:
        st.info(
            f"Fortaleza apresenta "
            f"{fortaleza_row['deficit_esgoto_por_km2'].values[0]:.2f} "
            "domicílios em déficit de esgoto por km² no recorte atual."
        )


with tab_lixo_dens:
    st.markdown("#### Lixo inadequado x densidade")

    # Cria os quartis de densidade
    filtrado["dens_quartil"] = pd.qcut(
        filtrado["densidade"],
        min(4, filtrado["densidade"].nunique()),
        duplicates="drop"
    )

    # Calcula a média de lixo inadequado por quartil
    medias = (
        filtrado.groupby("dens_quartil", observed=True)["pct_lixo_inadequado"]
        .mean()
        .round(2)
        .reset_index()
    )

    # Formata os intervalos dos quartis para apenas 2 casas decimais
    def formatar_intervalo(intervalo):
        return (
            f"({intervalo.left:.2f}, {intervalo.right:.2f}]"
        )

    medias["dens_quartil"] = medias["dens_quartil"].apply(
        formatar_intervalo
    )

    fig_lixo_dens = px.bar(
        medias,
        x="dens_quartil",
        y="pct_lixo_inadequado",
        labels={
            "dens_quartil": "Quartil de densidade (hab/km²)",
            "pct_lixo_inadequado": "% lixo inadequado",
        },
    )

    fig_lixo_dens.update_layout(
        yaxis=dict(
            tickformat=".2f"
        )
    )

    fig_lixo_dens.update_traces(
        texttemplate="%{y:.2f}%",
        textposition="outside",
        hovertemplate=(
            "%{x}<br>"
            "Lixo inadequado: %{y:.2f}%"
            "<extra></extra>"
        )
    )

    st.plotly_chart(fig_lixo_dens, width="stretch")

st.divider()

# --- 2) Água x esgoto ------------------------------------------------------
st.subheader("💧 Água x esgoto")
st.markdown("#### Descompasso entre água e esgoto")
filtrado["gap_agua_esgoto"] = (
    filtrado["pct_esgoto_inadequado"] - filtrado["pct_agua_sem_rede"]
)
top_gap = filtrado.sort_values("gap_agua_esgoto", ascending=False).head(15)
fig_gap = px.bar(
    top_gap, x="gap_agua_esgoto", y="municipio", orientation="h",
    color="gap_agua_esgoto", color_continuous_scale="Reds",
    labels={"gap_agua_esgoto": "Gap esgoto - água (p.p.)", "municipio": ""},
)
fig_gap.update_layout(
    yaxis=dict(autorange="reversed"), coloraxis_showscale=False, height=500
)
fig_gap.update_traces(texttemplate="%{x:.2f}", textposition="outside")
st.plotly_chart(fig_gap, width="stretch")
st.info(
    f"Gap médio no recorte atual: {filtrado['gap_agua_esgoto'].mean():.2f} p.p."
)

st.divider()

# --- 3) Distância até Fortaleza + Até os melhores têm esgoto ruim (abas) ---
st.subheader("📍 Distância até Fortaleza e desempenho dos melhores")
tab_dist, tab_melhores = st.tabs([
    "Distância até Fortaleza",
    "Até os melhores têm esgoto ruim",
])

with tab_dist:
    st.markdown("#### Proximidade com Fortaleza e cobertura de esgoto")
    fig_dist = px.scatter(
        filtrado, x="dist_fortaleza_km", y="pct_esgoto_rede",
        hover_name="municipio", color="categoria_desempenho",
        color_discrete_map=CORES_DESEMPENHO,
        labels={
            "dist_fortaleza_km": "Distância até Fortaleza (km, centroide)",
            "pct_esgoto_rede": "% esgoto rede geral",
            "categoria_desempenho": "Desempenho geral",
        },
    )
    st.plotly_chart(fig_dist, width="stretch")
    corr = filtrado["dist_fortaleza_km"].corr(filtrado["pct_esgoto_rede"])
    st.info(f"Correlação no recorte atual: {corr:.2f}.")

with tab_melhores:
    st.markdown("#### Até os melhores têm esgoto ruim")
    melhores10 = filtrado[
        filtrado["categoria_desempenho"] == "Entre os 10 melhores"
    ].sort_values("indice_deficit")
    if melhores10.empty:
        st.warning(
            "Nenhum dos 10 melhores municípios do estado está no recorte "
            "filtrado atual."
        )
    else:
        fig_melhores = px.bar(
            melhores10.melt(
                id_vars="municipio",
                value_vars=[
                    "pct_agua_sem_rede",
                    "pct_esgoto_inadequado",
                    "pct_lixo_inadequado",
                ],
                var_name="dimensao", value_name="pct",
            ),
            x="municipio", y="pct", color="dimensao", barmode="group",
            color_discrete_map={
                "pct_agua_sem_rede": "#2a78d6",
                "pct_esgoto_inadequado": "#c0392b",
                "pct_lixo_inadequado": "#e08e00",
            },
            labels={"pct": "%", "municipio": "", "dimensao": "Dimensão"},
        )
        fig_melhores.update_traces(texttemplate="%{y:.2f}%", textposition="outside")
        st.plotly_chart(fig_melhores, width="stretch")
        st.info(
            f"Esgoto inadequado nos 10 melhores: "
            f"{melhores10['pct_esgoto_inadequado'].mean():.2f}%."
        )

st.divider()

# --- 4) Correlação entre dimensões -----------------------------------------
st.subheader("🔬 Correlação entre dimensões")
st.markdown("#### Correlação entre água, esgoto e lixo")
corr_dim = filtrado[
    ["pct_agua_sem_rede", "pct_esgoto_inadequado", "pct_lixo_inadequado"]
].corr().round(2)
fig_corr = px.imshow(
    corr_dim, text_auto=True, color_continuous_scale="RdBu_r",
    zmin=-1, zmax=1, labels=dict(color="Correlação"),
    x=["Água", "Esgoto", "Lixo"], y=["Água", "Esgoto", "Lixo"],
)
st.plotly_chart(fig_corr, width="stretch")
st.info(
    "A matriz apresenta as correlações lineares entre as três dimensões. "
    "Correlação não implica causalidade."
)

st.divider()

# ---------------------------------------------------------------------------
# Fontes e metodologia
# ---------------------------------------------------------------------------
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

**Organização final das análises:**
1. Revisão metodológica — categorias de água, esgoto e lixo (3 abas)
2. KPIs gerais
3. Comparação territorial e municípios prioritários
4. Cruzamentos entre bases (um por seção):
   a) Concentração por km² + lixo e densidade (abas)
   b) Água x esgoto
   c) Distância até Fortaleza + até os melhores têm esgoto ruim (abas)
   d) Correlação entre dimensões

**Limitações:**
- O índice de déficit é uma construção exploratória da equipe (média
  entre municípios, sem ponderar por número de domicílios), não um
  indicador oficial — sujeito a revisão de pesos.
- As 5 geometrias com auto-interseção na malha simplificada (Acaraú,
  Barbalha, Crateús, Limoeiro do Norte e Mauriti) foram corrigidas em
  tempo de execução com `GeoSeries.make_valid()`; o arquivo original em
  `raw/` permanece intacto.
- As categorias medem o tipo de solução declarada, não comprovam
  potabilidade da água, tratamento efetivo do esgoto, nem destino final
  ambientalmente adequado do lixo.
- A distância até Fortaleza é calculada entre centroides (projeção
  métrica aproximada, EPSG:3857) — serve para comparação relativa entre
  municípios, não para medições cartográficas de precisão.
- "Fossa séptica não ligada à rede" e "outra forma" ainda não têm
  classificação definida como adequado/inadequado.
        """
    )