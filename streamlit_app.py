from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capm.config import AnalysisConfig, config_from_mapping, load_config
from capm.exports import export_outputs, format_percent, streamlit_fact_frame, summary_frame
from capm.model import run_analysis

CONFIG_DIR = ROOT / "configs"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


st.set_page_config(page_title="Analise CAPM", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    h1, h2, h3 { letter-spacing: 0; }
    div[data-testid="stMetric"] {
        border: 1px solid #d9e2ec;
        border-radius: 8px;
        padding: 12px 14px;
        background: #ffffff;
        min-height: 96px;
    }
    div[data-testid="stMetricValue"] { font-size: 1.45rem; }
    section[data-testid="stSidebar"] { border-right: 1px solid #d9e2ec; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def list_configs() -> list[Path]:
    return sorted(CONFIG_DIR.glob("*.toml"))


def selected_config() -> AnalysisConfig:
    configs = list_configs()
    labels = [path.stem for path in configs]
    default_index = labels.index("example") if "example" in labels else 0
    selected = st.sidebar.selectbox("Configuracao", labels, index=default_index if labels else None)
    if not selected:
        return config_from_mapping(
            {
                "ticker": "FICT3",
                "market": "MKT",
                "start": "2024-01-01",
                "end": "2024-12-31",
                "price_source": "offline",
                "risk_free_source": "csv",
                "asset_prices_csv": ROOT / "examples/offline/fict3_prices.csv",
                "market_prices_csv": ROOT / "examples/offline/market_prices.csv",
                "risk_free_csv": ROOT / "examples/offline/risk_free.csv",
            }
        )
    return load_config(CONFIG_DIR / f"{selected}.toml")


def uploaded_csv_path(uploaded_file: object | None, label: str) -> Path | None:
    if uploaded_file is None:
        return None
    if "capm_upload_dir" not in st.session_state:
        st.session_state.capm_upload_dir = tempfile.TemporaryDirectory(prefix="capm-streamlit-")
    upload_dir = Path(st.session_state.capm_upload_dir.name)
    destination = upload_dir / f"{label}.csv"
    content = uploaded_file.getvalue()
    if destination.exists() and destination.read_bytes() == content:
        return destination
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.replace(destination)
    return destination


base_config = selected_config()

st.title(base_config.presentation.title or "Analise CAPM")
st.caption("Ferramenta generica de analise CAPM com classificacao academica.")

with st.sidebar:
    st.subheader("Parametros")
    asset_name = st.text_input("Nome do ativo", value=base_config.asset_name or "")
    ticker = st.text_input("Ticker do ativo", value=base_config.ticker)
    market = st.text_input("Ticker do mercado", value=base_config.market)
    start = st.date_input("Data inicial", value=pd.Timestamp(base_config.start).date())
    end = st.date_input("Data final", value=pd.Timestamp(base_config.end).date())
    price_source = st.selectbox(
        "Fonte de precos",
        ["offline", "csv", "yahoo", "b3"],
        index=["offline", "csv", "yahoo", "b3"].index(base_config.price_source),
    )
    risk_free_source = st.selectbox(
        "Taxa livre de risco",
        ["csv", "annual_constant", "bcb_sgs"],
        index=["csv", "annual_constant", "bcb_sgs"].index(base_config.risk_free_source),
    )
    rf_constant = st.number_input(
        "RF anual constante (%)",
        value=float(base_config.risk_free_annual_rate or 10.0),
        step=0.10,
        format="%.2f",
    )
    asset_upload = None
    market_upload = None
    risk_free_upload = None
    if price_source == "csv":
        asset_upload = st.file_uploader("CSV de precos do ativo", type="csv")
        market_upload = st.file_uploader("CSV de precos do mercado", type="csv")
    if risk_free_source == "csv":
        risk_free_upload = st.file_uploader("CSV da taxa livre de risco", type="csv")
    run_button = st.button("Executar analise", type="primary", width="stretch")

asset_prices_csv = uploaded_csv_path(asset_upload, "asset_prices")
market_prices_csv = uploaded_csv_path(market_upload, "market_prices")
risk_free_csv = uploaded_csv_path(risk_free_upload, "risk_free")

if asset_prices_csv is None and base_config.price_source in {"offline", "csv"}:
    asset_prices_csv = base_config.asset_prices_csv
if market_prices_csv is None and base_config.price_source in {"offline", "csv"}:
    market_prices_csv = base_config.market_prices_csv
if risk_free_csv is None and base_config.risk_free_source == "csv":
    risk_free_csv = base_config.risk_free_csv


config = AnalysisConfig(
    asset_name=asset_name or None,
    ticker=ticker,
    market=market,
    start=start.isoformat(),
    end=end.isoformat(),
    price_source=price_source,
    risk_free_source=risk_free_source,
    output_dir=base_config.output_dir,
    slug=base_config.slug,
    asset_prices_csv=asset_prices_csv,
    market_prices_csv=market_prices_csv,
    risk_free_csv=risk_free_csv,
    risk_free_annual_rate=rf_constant,
    bcb_series=base_config.bcb_series,
    b3_cotahist_dir=base_config.b3_cotahist_dir,
    ticker_history=base_config.ticker_history,
    presentation=base_config.presentation,
)


if "capm_result" not in st.session_state or run_button:
    try:
        st.session_state.capm_result = run_analysis(config)
        st.session_state.capm_paths = export_outputs(st.session_state.capm_result)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

result = st.session_state.capm_result
paths = st.session_state.capm_paths
summary = summary_frame(result)
fact = streamlit_fact_frame(result)

cols = st.columns(5)
cols[0].metric("Beta OLS", f"{result.regression.beta:.4f}")
cols[1].metric("Alfa", f"{result.regression.alpha:.4f}")
cols[2].metric("R2", f"{result.regression.r_squared:.4f}")
cols[3].metric("CAPM preciso", format_percent(result.metrics.capm_precise))
cols[4].metric("Classificacao", result.metrics.recommendation)

st.caption(result.config.presentation.disclaimer)

tab_summary, tab_series, tab_charts, tab_downloads = st.tabs(
    ["Resumo", "Series", "Graficos", "Arquivos"]
)

with tab_summary:
    st.dataframe(
        summary[["Grupo", "Indicador", "ValorFormatado", "Unidade", "Observacao"]].rename(
            columns={"ValorFormatado": "Valor", "Observacao": "Observacao"}
        ),
        hide_index=True,
        width="stretch",
    )

with tab_series:
    st.line_chart(fact.set_index("Data")[["RetornoAcumuladoAcao", "RetornoAcumuladoMercado"]])
    st.dataframe(fact, hide_index=True, width="stretch")

with tab_charts:
    chart_cols = st.columns(2)
    chart_cols[0].image(str(paths["returns_png"]), caption="Retornos mensais", width="stretch")
    chart_cols[1].image(str(paths["regression_png"]), caption="Regressao CAPM", width="stretch")

with tab_downloads:
    for label, key, mime in [
        ("Excel principal", "analysis_xlsx", MIME_XLSX),
        ("Excel resultado", "result_xlsx", MIME_XLSX),
        ("Excel dados", "data_xlsx", MIME_XLSX),
        ("Grafico de retornos", "returns_png", "image/png"),
        ("Grafico de regressao", "regression_png", "image/png"),
    ]:
        path = paths[key]
        st.download_button(label, path.read_bytes(), file_name=path.name, mime=mime, width="stretch")
