from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
DADOS_STREAMLIT_DIR = DADOS_DIR / "streamlit"
GRAFICOS_DIR = BASE_DIR / "graficos"
RELATORIO_DIR = BASE_DIR / "relatorio"

CAMINHO_FATO = DADOS_STREAMLIT_DIR / "fato_capm_mensal.csv"
CAMINHO_RESUMO = DADOS_STREAMLIT_DIR / "resumo_indicadores.csv"
CAMINHO_CALENDARIO = DADOS_STREAMLIT_DIR / "dimensao_calendario.csv"
CAMINHO_FONTES = DADOS_STREAMLIT_DIR / "metodologia_fontes.csv"

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


st.set_page_config(
    page_title="CAPM Embraer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        letter-spacing: 0;
    }
    div[data-testid="stMetric"] {
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        padding: 14px 16px;
        background: #ffffff;
        min-height: 106px;
    }
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p {
        color: #334e68;
        white-space: normal;
    }
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] div {
        color: #102a43;
        font-size: 1.65rem;
        line-height: 1.15;
        white-space: normal;
        overflow: visible;
        text-overflow: clip;
    }
    section[data-testid="stSidebar"] {
        border-right: 1px solid #d9e2ec;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def carregar_bases() -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, list[str]]:
    caminhos = {
        "base mensal": CAMINHO_FATO,
        "resumo": CAMINHO_RESUMO,
        "metodologia": CAMINHO_FONTES,
    }
    faltantes = [nome for nome, caminho in caminhos.items() if not caminho.exists()]

    if faltantes:
        return None, None, None, faltantes

    fato = pd.read_csv(CAMINHO_FATO, parse_dates=["Data"])
    resumo = pd.read_csv(CAMINHO_RESUMO)
    fontes = pd.read_csv(CAMINHO_FONTES)

    fato = fato.sort_values("Data").reset_index(drop=True)
    resumo["ValorNumerico"] = pd.to_numeric(resumo["ValorNumerico"], errors="coerce")

    return fato, resumo, fontes, []


def indicador_texto(resumo: pd.DataFrame, nome: str, padrao: str = "-") -> str:
    linha = resumo.loc[resumo["Indicador"].eq(nome)]
    if linha.empty:
        return padrao
    valor = linha.iloc[0]["ValorFormatado"]
    return padrao if pd.isna(valor) else str(valor)


def indicador_numero(resumo: pd.DataFrame, nome: str, padrao: float = 0.0) -> float:
    linha = resumo.loc[resumo["Indicador"].eq(nome)]
    if linha.empty:
        return padrao
    valor = linha.iloc[0]["ValorNumerico"]
    return padrao if pd.isna(valor) else float(valor)


def formatar_percentual(valor: float) -> str:
    return f"{valor * 100:.2f}%"


def formatar_numero(valor: float) -> str:
    return f"{valor:.4f}"


def formatar_moeda(valor: float) -> str:
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def recomendacao_por_diferenca(diferenca: float) -> str:
    if diferenca > 0:
        return "Compra"
    if diferenca < 0:
        return "Venda"
    return "Manutenção"


def botao_download(rotulo: str, caminho: Path, mime: str) -> None:
    if caminho.exists():
        st.download_button(
            label=rotulo,
            data=caminho.read_bytes(),
            file_name=caminho.name,
            mime=mime,
            width="stretch",
        )
    else:
        st.button(rotulo, disabled=True, width="stretch")


def exibir_imagem(caminho: Path, legenda: str) -> None:
    if caminho.exists():
        st.image(str(caminho), caption=legenda, width="stretch")
    else:
        st.info(f"Arquivo não encontrado: {caminho.name}")


fato, resumo, fontes, faltantes = carregar_bases()

st.title("CAPM Embraer")
st.caption("EMBJ3 | Janeiro/2021 a Dezembro/2025")

if faltantes:
    st.error("Bases do painel não encontradas: " + ", ".join(faltantes))
    st.code(r".\.venv\Scripts\python.exe .\main.py --yes", language="powershell")
    st.stop()

assert fato is not None
assert resumo is not None
assert fontes is not None

periodos = fato["AnoMes"].tolist()
periodo_selecionado = st.sidebar.selectbox(
    "Mês de destaque",
    periodos,
    index=len(periodos) - 1,
)
linha_periodo = fato.loc[fato["AnoMes"].eq(periodo_selecionado)].iloc[0]

anos = sorted(fato["Ano"].unique().tolist())
anos_selecionados = st.sidebar.multiselect("Anos", anos, default=anos)
base_filtrada = fato.loc[fato["Ano"].isin(anos_selecionados)].copy()

st.sidebar.metric("Preço EMBJ3", formatar_moeda(linha_periodo["PrecoAcao"]))
st.sidebar.metric("Retorno no mês", formatar_percentual(linha_periodo["RetornoAcao"]))
st.sidebar.metric("Ibovespa no mês", formatar_percentual(linha_periodo["RetornoMercado"]))

beta_capm = indicador_numero(resumo, "Beta calculado usado no CAPM")
retorno_acao = indicador_numero(resumo, "Retorno médio mensal da ação")
retorno_mercado = indicador_numero(resumo, "Retorno médio mensal do mercado")
taxa_livre = indicador_numero(resumo, "Selic média mensal")
retorno_capm = indicador_numero(resumo, "Retorno esperado CAPM mensal")
diferenca_capm = indicador_numero(resumo, "Diferença observado menos CAPM mensal")
recomendacao = indicador_texto(resumo, "Recomendação final")
r_quadrado = indicador_numero(resumo, "R²")

col_beta, col_acao, col_capm, col_diff, col_rec = st.columns(5)
col_beta.metric("Beta CAPM", formatar_numero(beta_capm))
col_acao.metric("Retorno médio", formatar_percentual(retorno_acao))
col_capm.metric("Retorno exigido", formatar_percentual(retorno_capm))
col_diff.metric("Diferença", formatar_percentual(diferenca_capm))
col_rec.metric("Recomendação", recomendacao)

tab_resumo, tab_calculadora, tab_series, tab_graficos, tab_metodologia, tab_arquivos = st.tabs(
    ["Resumo", "Calculadora", "Séries", "Gráficos", "Metodologia", "Arquivos"]
)

with tab_resumo:
    col_esq, col_dir = st.columns([1.15, 1])

    with col_esq:
        st.subheader("Indicadores")
        tabela_resumo = resumo[["Grupo", "Indicador", "ValorFormatado", "Unidade", "Observacao"]].rename(
            columns={
                "ValorFormatado": "Valor",
                "Observacao": "Observação",
            }
        )
        st.dataframe(tabela_resumo, hide_index=True, width="stretch")

    with col_dir:
        st.subheader("Retornos médios")
        comparativo = pd.DataFrame(
            {
                "Taxa mensal (%)": [
                    retorno_acao * 100,
                    retorno_capm * 100,
                    taxa_livre * 100,
                    retorno_mercado * 100,
                ]
            },
            index=["Embraer", "CAPM", "Selic", "Ibovespa"],
        )
        st.bar_chart(comparativo, width="stretch")

        st.subheader("Diagnóstico da regressão")
        reg_cols = st.columns(3)
        reg_cols[0].metric("Beta regressão", indicador_texto(resumo, "Beta da regressão com retornos excedentes"))
        reg_cols[1].metric("Alfa", indicador_texto(resumo, "Alfa"))
        reg_cols[2].metric("R²", formatar_numero(r_quadrado))

with tab_calculadora:
    st.subheader("Calculadora CAPM")
    calc_1, calc_2, calc_3, calc_4 = st.columns(4)
    beta_input = calc_1.number_input("Beta", value=beta_capm, step=0.01, format="%.4f")
    rf_input = calc_2.number_input(
        "Taxa livre mensal (%)",
        value=taxa_livre * 100,
        step=0.10,
        format="%.2f",
    )
    mercado_input = calc_3.number_input(
        "Retorno do mercado mensal (%)",
        value=retorno_mercado * 100,
        step=0.10,
        format="%.2f",
    )
    observado_input = calc_4.number_input(
        "Retorno observado mensal (%)",
        value=retorno_acao * 100,
        step=0.10,
        format="%.2f",
    )

    rf_decimal = rf_input / 100
    mercado_decimal = mercado_input / 100
    observado_decimal = observado_input / 100
    capm_calculado = rf_decimal + beta_input * (mercado_decimal - rf_decimal)
    diferenca_calculada = observado_decimal - capm_calculado
    recomendacao_calculada = recomendacao_por_diferenca(diferenca_calculada)

    calc_resultado = st.columns(3)
    calc_resultado[0].metric("Retorno CAPM calculado", formatar_percentual(capm_calculado))
    calc_resultado[1].metric("Diferença observada", formatar_percentual(diferenca_calculada))
    calc_resultado[2].metric("Resultado", recomendacao_calculada)

with tab_series:
    st.subheader("Série mensal")
    serie_retornos = (
        base_filtrada.set_index("Data")[["RetornoAcao", "RetornoMercado", "SelicMensal"]]
        .rename(
            columns={
                "RetornoAcao": "Embraer",
                "RetornoMercado": "Ibovespa",
                "SelicMensal": "Selic",
            }
        )
        * 100
    )
    st.line_chart(serie_retornos, width="stretch")

    tabela_mensal = base_filtrada[
        [
            "Data",
            "AnoMes",
            "PrecoAcao",
            "PrecoMercado",
            "RetornoAcao",
            "RetornoMercado",
            "SelicMensal",
            "ExcessoAcao",
            "ExcessoMercado",
            "RetornoAcumuladoAcao",
            "RetornoAcumuladoMercado",
        ]
    ].rename(
        columns={
            "PrecoAcao": "Preço Embraer",
            "PrecoMercado": "Ibovespa",
            "RetornoAcao": "Retorno Embraer",
            "RetornoMercado": "Retorno Ibovespa",
            "SelicMensal": "Selic",
            "ExcessoAcao": "Excesso Embraer",
            "ExcessoMercado": "Excesso Ibovespa",
            "RetornoAcumuladoAcao": "Acumulado Embraer",
            "RetornoAcumuladoMercado": "Acumulado Ibovespa",
        }
    )
    st.dataframe(
        tabela_mensal.style.format(
            {
                "Preço Embraer": "R$ {:.2f}",
                "Ibovespa": "{:.2f}",
                "Retorno Embraer": "{:.2%}",
                "Retorno Ibovespa": "{:.2%}",
                "Selic": "{:.2%}",
                "Excesso Embraer": "{:.2%}",
                "Excesso Ibovespa": "{:.2%}",
                "Acumulado Embraer": "{:.2%}",
                "Acumulado Ibovespa": "{:.2%}",
            }
        ),
        hide_index=True,
        width="stretch",
    )

with tab_graficos:
    col_graf_1, col_graf_2 = st.columns(2)
    with col_graf_1:
        exibir_imagem(
            GRAFICOS_DIR / "retornos_mensais_embraer_ibovespa.png",
            "Retornos mensais: Embraer x Ibovespa",
        )
    with col_graf_2:
        exibir_imagem(
            GRAFICOS_DIR / "regressao_capm.png",
            "Regressão CAPM: Embraer x Ibovespa",
        )

    st.subheader("Retorno acumulado")
    acumulado = (
        base_filtrada.set_index("Data")[["RetornoAcumuladoAcao", "RetornoAcumuladoMercado"]]
        .rename(
            columns={
                "RetornoAcumuladoAcao": "Embraer",
                "RetornoAcumuladoMercado": "Ibovespa",
            }
        )
        * 100
    )
    st.line_chart(acumulado, width="stretch")

with tab_metodologia:
    st.subheader("Fontes e limitações")
    st.dataframe(fontes, hide_index=True, width="stretch")

with tab_arquivos:
    st.subheader("Downloads")
    arq_cols = st.columns(3)
    with arq_cols[0]:
        botao_download("Excel principal", DADOS_DIR / "analise_capm_embraer.xlsx", MIME_XLSX)
        botao_download("Excel resultado", DADOS_DIR / "resultado_capm_embraer.xlsx", MIME_XLSX)
    with arq_cols[1]:
        botao_download("Relatório Word", RELATORIO_DIR / "nota_tecnica_capm_embraer.docx", MIME_DOCX)
        botao_download("Base mensal CSV", CAMINHO_FATO, "text/csv")
    with arq_cols[2]:
        botao_download("Resumo CSV", CAMINHO_RESUMO, "text/csv")
        botao_download("Calendário CSV", CAMINHO_CALENDARIO, "text/csv")
        botao_download("Metodologia CSV", CAMINHO_FONTES, "text/csv")

    img_cols = st.columns(2)
    with img_cols[0]:
        botao_download(
            "Gráfico retornos PNG",
            GRAFICOS_DIR / "retornos_mensais_embraer_ibovespa.png",
            "image/png",
        )
    with img_cols[1]:
        botao_download("Gráfico regressão PNG", GRAFICOS_DIR / "regressao_capm.png", "image/png")
