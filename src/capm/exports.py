from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

_MPLCONFIGDIR = Path(tempfile.gettempdir()) / "capm-matplotlib"
_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPLCONFIGDIR))

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from capm.model import AnalysisResult

_EXCEL_CREATED_AT = datetime(2026, 1, 1, 0, 0, 0)


def format_percent(value: float) -> str:
    return f"{value:.2%}"


def summary_frame(result: AnalysisResult) -> pd.DataFrame:
    cfg = result.config
    metrics = result.metrics
    reg = result.regression
    cov = result.covariance
    rows = [
        ("Identificacao", "Ativo", np.nan, cfg.asset_name or cfg.ticker, "texto", "Nome configurado do ativo."),
        ("Identificacao", "Ticker do ativo", np.nan, cfg.ticker, "texto", "Ticker usado para coleta ou rotulo."),
        ("Identificacao", "Ticker do mercado", np.nan, cfg.market, "texto", "Proxy de mercado da analise."),
        ("Risco", "Beta calculado usado no CAPM", reg.beta, f"{reg.beta:.4f}", "decimal", "Coeficiente angular da OLS dos retornos excedentes."),
        ("Risco", "Beta covariancia/variancia diagnostico", cov.beta, f"{cov.beta:.4f}", "decimal", "Diagnostico; nao usado como beta principal."),
        ("Risco", "Covariancia ativo-mercado", cov.covariance, f"{cov.covariance:.8f}", "decimal", "Diagnostico dos retornos mensais brutos."),
        ("Risco", "Variancia do mercado", cov.market_variance, f"{cov.market_variance:.8f}", "decimal", "Diagnostico dos retornos mensais do mercado."),
        ("Regressao", "Alfa", reg.alpha, f"{reg.alpha:.4f}", "decimal", "Intercepto mensal da regressao."),
        ("Regressao", "R2", reg.r_squared, f"{reg.r_squared:.4f}", "decimal", "Coeficiente de determinacao."),
        ("Retorno", "Retorno anualizado do ativo", metrics.asset_annualized_return, format_percent(metrics.asset_annualized_return), "% ao ano", "Calculado pelo periodo efetivo dos precos usados."),
        ("Retorno", "Retorno anualizado do mercado", metrics.market_annualized_return, format_percent(metrics.market_annualized_return), "% ao ano", "Calculado pelo periodo efetivo dos precos usados."),
        ("Retorno", "Taxa livre anual media", metrics.rf, format_percent(metrics.rf), "% ao ano", "Media da serie anual informada, dividida por 100."),
        ("Retorno", "Taxa livre total no periodo", metrics.rf_total, format_percent(metrics.rf_total), "% periodo", "Produto dos fatores mensais menos 1."),
        ("CAPM", "CAPM preciso anual", metrics.capm_precise, format_percent(metrics.capm_precise), "% ao ano", "RF + beta * (RM - RF)."),
        ("CAPM", "CAPM arredondado metodologia academica", metrics.capm_academic, format_percent(metrics.capm_academic), "% ao ano", "round(CAPM preciso, 3)."),
        ("CAPM", "Valor usado na classificacao", metrics.classification_value, format_percent(metrics.classification_value), "% ao ano", "Classificacao academica usa o valor arredondado."),
        ("CAPM", "Diferenca observado menos CAPM academico", metrics.difference, format_percent(metrics.difference), "% ao ano", "Retorno anualizado do ativo menos CAPM arredondado."),
        ("Resultado", "Classificacao academica", np.nan, metrics.recommendation, "texto", cfg.presentation.disclaimer),
        ("Base", "Quantidade de retornos mensais", len(result.base), str(len(result.base)), "meses", "Observacoes apos pct_change e alinhamento."),
        ("Base", "Periodo em anos", metrics.years, f"{metrics.years:.4f}", "anos", "Dias entre as datas de precos efetivamente usadas dividido por 365."),
    ]
    return pd.DataFrame(rows, columns=["Grupo", "Indicador", "ValorNumerico", "ValorFormatado", "Unidade", "Observacao"])


def streamlit_fact_frame(result: AnalysisResult) -> pd.DataFrame:
    base = result.base.copy().reset_index(names="Data")
    fact = pd.DataFrame()
    fact["Data"] = base["Data"]
    fact["Ano"] = fact["Data"].dt.year
    fact["Mes"] = fact["Data"].dt.month
    fact["AnoMes"] = fact["Data"].dt.strftime("%Y-%m")
    fact["Ativo"] = result.config.asset_name or result.config.ticker
    fact["TickerAtual"] = result.config.ticker
    fact["TickerAcao"] = base["ticker_acao"].fillna(result.config.ticker)
    fact["IndiceMercado"] = result.config.market
    fact["PrecoAcao"] = base["preco_acao"]
    fact["PrecoMercado"] = base["preco_mercado"]
    fact["RetornoAcao"] = base["retorno_ativo"]
    fact["RetornoMercado"] = base["retorno_mercado"]
    fact["RFAnual"] = base["rf_anual"] / 100
    fact["RFMensal"] = base["rf_mensal"]
    fact["FatorRFMensal"] = base["fator_rf_mensal"]
    fact["ExcessoAcao"] = base["excesso_ativo"]
    fact["ExcessoMercado"] = base["excesso_mercado"]
    fact["RetornoAcumuladoAcao"] = (1 + fact["RetornoAcao"]).cumprod() - 1
    fact["RetornoAcumuladoMercado"] = (1 + fact["RetornoMercado"]).cumprod() - 1
    return fact


def methodology_frame(result: AnalysisResult) -> pd.DataFrame:
    cfg = result.config
    return pd.DataFrame(
        [
            {
                "Item": "Ativo",
                "Descricao": "Precos de fechamento do ativo conforme fonte configurada.",
                "Fonte": cfg.price_source,
                "Limitacao": "Precos nao ajustados automaticamente por proventos, salvo escolha do provedor.",
            },
            {
                "Item": "Mercado",
                "Descricao": "Proxy de mercado da analise CAPM.",
                "Fonte": cfg.market,
                "Limitacao": "Sujeito a disponibilidade da fonte configurada.",
            },
            {
                "Item": "Taxa livre de risco",
                "Descricao": "Taxa anual convertida para taxa mensal nos retornos excedentes.",
                "Fonte": cfg.risk_free_source,
                "Limitacao": "Usada como proxy academica da taxa livre de risco.",
            },
            {
                "Item": "Aviso",
                "Descricao": cfg.presentation.disclaimer,
                "Fonte": "Projeto CAPM",
                "Limitacao": "Nao substitui analise profissional.",
            },
        ]
    )


def export_outputs(result: AnalysisResult) -> dict[str, Path]:
    output_dir = result.config.output_dir
    streamlit_dir = output_dir / "streamlit" / result.slug
    charts_dir = output_dir / "graficos"
    output_dir.mkdir(parents=True, exist_ok=True)
    streamlit_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    summary = summary_frame(result)
    fact = streamlit_fact_frame(result)
    methodology = methodology_frame(result)

    analysis_xlsx = output_dir / f"analise_capm_{result.slug}.xlsx"
    result_xlsx = output_dir / f"resultado_capm_{result.slug}.xlsx"
    data_xlsx = output_dir / f"dados_capm_{result.slug}.xlsx"
    with pd.ExcelWriter(
        analysis_xlsx,
        engine="xlsxwriter",
        date_format="yyyy-mm-dd",
        datetime_format="yyyy-mm-dd",
    ) as writer:
        _set_workbook_properties(writer)
        summary.to_excel(writer, sheet_name="Resumo", index=False)
        _format_worksheet(writer, "Resumo", summary)
        fact.to_excel(writer, sheet_name="Base mensal", index=False)
        _format_worksheet(writer, "Base mensal", fact)
        monthly_prices_frame = result.monthly_price_base.reset_index(names="Data")
        monthly_prices_frame.to_excel(writer, sheet_name="Precos mensais", index=False)
        _format_worksheet(writer, "Precos mensais", monthly_prices_frame)
    _write_single_sheet_excel(result_xlsx, summary, sheet_name="Resumo")
    _write_single_sheet_excel(data_xlsx, fact, sheet_name="Base mensal")

    fact_path = streamlit_dir / "fato_capm_mensal.csv"
    summary_path = streamlit_dir / "resumo_indicadores.csv"
    methodology_path = streamlit_dir / "metodologia_fontes.csv"
    _write_csv_if_changed(
        fact_path,
        fact,
        date_format="%Y-%m-%d",
    )
    _write_csv_if_changed(summary_path, summary)
    _write_csv_if_changed(
        methodology_path,
        methodology,
    )

    returns_png = charts_dir / f"retornos_mensais_{result.slug}.png"
    regression_png = charts_dir / f"regressao_capm_{result.slug}.png"
    _plot_returns(result, returns_png)
    _plot_regression(result, regression_png)

    return {
        "analysis_xlsx": analysis_xlsx,
        "result_xlsx": result_xlsx,
        "data_xlsx": data_xlsx,
        "streamlit_fact": fact_path,
        "streamlit_summary": summary_path,
        "streamlit_methodology": methodology_path,
        "returns_png": returns_png,
        "regression_png": regression_png,
    }


def _set_workbook_properties(writer: pd.ExcelWriter) -> None:
    writer.book.set_properties(
        {
            "author": "Projeto CAPM",
            "company": "Projeto CAPM",
            "created": _EXCEL_CREATED_AT,
        }
    )


def _write_single_sheet_excel(path: Path, frame: pd.DataFrame, *, sheet_name: str) -> None:
    with pd.ExcelWriter(
        path,
        engine="xlsxwriter",
        date_format="yyyy-mm-dd",
        datetime_format="yyyy-mm-dd",
    ) as writer:
        _set_workbook_properties(writer)
        frame.to_excel(writer, sheet_name=sheet_name, index=False)
        _format_worksheet(writer, sheet_name, frame)


def _format_worksheet(writer: pd.ExcelWriter, sheet_name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#1F4E78",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )
    text = workbook.add_format({"valign": "top"})
    wrapped_text = workbook.add_format({"valign": "top", "text_wrap": True})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd", "valign": "top"})
    integer_format = workbook.add_format({"num_format": "0", "valign": "top"})
    decimal_format = workbook.add_format({"num_format": "0.00000000", "valign": "top"})

    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, len(frame), len(frame.columns) - 1)
    worksheet.set_row(0, 24)

    for column_number, column_name in enumerate(frame.columns):
        worksheet.write(0, column_number, column_name, header)
        values = frame[column_name].dropna().astype(str)
        content_width = max((len(value) for value in values), default=0)
        width = min(max(len(str(column_name)), content_width) + 2, 48)
        if pd.api.types.is_datetime64_any_dtype(frame[column_name]):
            cell_format = date_format
            width = max(width, 12)
        elif pd.api.types.is_integer_dtype(frame[column_name]) or column_name in {"Ano", "Mes"}:
            cell_format = integer_format
            width = max(width, 10)
        elif pd.api.types.is_numeric_dtype(frame[column_name]):
            cell_format = decimal_format
            width = max(width, 16)
        elif column_name in {"Observacao", "Descricao", "Limitacao"}:
            cell_format = wrapped_text
            width = max(width, 32)
        else:
            cell_format = text
        worksheet.set_column(column_number, column_number, width, cell_format)


def _write_csv_if_changed(
    path: Path,
    frame: pd.DataFrame,
    *,
    date_format: str | None = None,
) -> None:
    content = frame.to_csv(
        index=False,
        date_format=date_format,
        lineterminator="\n",
    ).encode("utf-8")
    if path.exists() and path.read_bytes() == content:
        return
    path.write_bytes(content)


def _plot_returns(result: AnalysisResult, path: Path) -> None:
    fact = streamlit_fact_frame(result)
    plt.figure(figsize=(10, 5))
    plt.plot(fact["Data"], fact["RetornoAcao"], label=result.config.asset_name or result.config.ticker)
    plt.plot(fact["Data"], fact["RetornoMercado"], label=result.config.market)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Retornos mensais")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _plot_regression(result: AnalysisResult, path: Path) -> None:
    base = result.base
    x = base["excesso_mercado"]
    y = base["excesso_ativo"]
    line = result.regression.alpha + result.regression.beta * x
    plt.figure(figsize=(7, 5))
    plt.scatter(x, y, alpha=0.75)
    plt.plot(x, line, color="red")
    plt.title("Regressao CAPM")
    plt.xlabel("Excesso do mercado")
    plt.ylabel("Excesso do ativo")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
