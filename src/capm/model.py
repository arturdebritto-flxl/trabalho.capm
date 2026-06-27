from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from capm.config import AnalysisConfig
from capm.data_sources import load_asset_prices, load_market_prices, load_risk_free
from capm.regression import CovarianceDiagnostic, RegressionResult, covariance_beta, ols_excess_returns
from capm.returns import annualized_return, monthly_prices, percent_returns, years_between
from capm.validation import ensure_enough_observations, safe_slug, validate_config


@dataclass(frozen=True)
class CapmMetrics:
    rf: float
    rf_total: float
    rm: float
    asset_annualized_return: float
    market_annualized_return: float
    asset_total_return: float
    market_total_return: float
    capm_precise: float
    capm_academic: float
    classification_value: float
    difference: float
    recommendation: str
    years: float


@dataclass(frozen=True)
class AnalysisResult:
    config: AnalysisConfig
    slug: str
    base: pd.DataFrame
    monthly_price_base: pd.DataFrame
    regression: RegressionResult
    covariance: CovarianceDiagnostic
    metrics: CapmMetrics


def _format_month_list(index: pd.DatetimeIndex, *, limit: int = 5) -> str:
    values = index.sort_values()
    if len(values) > limit:
        values = values[:limit]
    return ", ".join(value.strftime("%Y-%m-%d") for value in values)


def _validate_same_monthly_index(reference: pd.DatetimeIndex, other: pd.DatetimeIndex, *, label: str) -> None:
    if reference.equals(other):
        return
    missing = reference.difference(other)
    extra = other.difference(reference)
    parts: list[str] = []
    if len(missing):
        parts.append(f"faltam {_format_month_list(missing)}")
    if len(extra):
        parts.append(f"sobram {_format_month_list(extra)}")
    raise ValueError(f"Desalinhamento mensal entre as series para {label}: " + "; ".join(parts))


def _reject_missing_months(frame: pd.DataFrame, column: str, *, label: str) -> None:
    missing = frame.index[frame[column].isna()]
    if len(missing):
        raise ValueError(
            f"Desalinhamento mensal: {label} sem observacao em meses obrigatorios: "
            f"{_format_month_list(missing)}"
        )


def _monthly_price_frame(frame: pd.DataFrame, *, price_column: str, renamed_column: str) -> pd.DataFrame:
    monthly = monthly_prices(frame[[price_column]]).rename(columns={price_column: renamed_column})
    _reject_missing_months(monthly, renamed_column, label=renamed_column)
    return monthly


def _monthly_asset_frame(frame: pd.DataFrame) -> pd.DataFrame:
    monthly = monthly_prices(frame[["preco", "ticker"]]).rename(
        columns={"preco": "preco_acao", "ticker": "ticker_acao"}
    )
    _reject_missing_months(monthly, "preco_acao", label="preco_acao")
    _reject_missing_months(monthly, "ticker_acao", label="ticker_acao")
    return monthly


def build_monthly_base(
    asset_prices: pd.DataFrame,
    market_prices: pd.DataFrame,
    risk_free: pd.DataFrame,
) -> pd.DataFrame:
    if "preco_acao" in asset_prices.columns:
        asset = asset_prices.sort_index()
    else:
        asset = _monthly_asset_frame(asset_prices)
    if "preco_mercado" in market_prices.columns:
        market = market_prices.sort_index()
    else:
        market = _monthly_price_frame(market_prices, price_column="preco", renamed_column="preco_mercado")
    if "rf_mensal" in risk_free.columns and "fator_rf_mensal" in risk_free.columns:
        rf = risk_free.sort_index()
    else:
        rf = risk_free.sort_index().copy()
        if "rf_anual" not in rf.columns:
            raise ValueError("Taxa livre de risco precisa da coluna rf_anual.")
        rf["rf_mensal"] = (1 + rf["rf_anual"] / 100) ** (1 / 12) - 1
        rf["fator_rf_mensal"] = 1 + rf["rf_mensal"]
    _validate_same_monthly_index(asset.index, market.index, label="ativo e mercado")
    _validate_same_monthly_index(asset.index, rf.index, label="ativo/mercado e taxa livre de risco")
    base = asset.join(market, how="inner").join(rf[["rf_anual", "rf_mensal", "fator_rf_mensal"]], how="inner")
    ensure_enough_observations(base.dropna(subset=["preco_acao", "preco_mercado"]), minimum=3, label="precos mensais")
    return base.dropna(subset=["preco_acao", "preco_mercado", "rf_mensal"])


def compute_return_base(monthly_base: pd.DataFrame) -> pd.DataFrame:
    base = monthly_base.copy()
    numeric_columns = [
        "preco_acao",
        "preco_mercado",
        "rf_anual",
        "rf_mensal",
        "fator_rf_mensal",
    ]
    if not np.isfinite(base[numeric_columns].to_numpy(dtype=float)).all():
        raise ValueError("Base mensal possui valores nulos ou infinitos.")
    if (base[["preco_acao", "preco_mercado", "fator_rf_mensal"]] <= 0).any().any():
        raise ValueError("Precos e fator da taxa livre devem ser positivos.")
    base["retorno_ativo"] = percent_returns(base["preco_acao"])
    base["retorno_mercado"] = percent_returns(base["preco_mercado"])
    base["excesso_ativo"] = base["retorno_ativo"] - base["rf_mensal"]
    base["excesso_mercado"] = base["retorno_mercado"] - base["rf_mensal"]
    base = base.dropna(subset=["retorno_ativo", "retorno_mercado", "excesso_ativo", "excesso_mercado"])
    ensure_enough_observations(base, minimum=2, label="retornos mensais")
    return base


def classify_academic(asset_return: float, capm_academic: float) -> tuple[str, float]:
    difference = asset_return - capm_academic
    if difference > 0:
        return "Compra", difference
    if difference < 0:
        return "Venda", difference
    return "Manutencao", difference


def calculate_metrics(base: pd.DataFrame, beta: float) -> CapmMetrics:
    start_price_date = pd.Timestamp(base.index.min())
    end_price_date = pd.Timestamp(base.index.max())
    years = years_between(start_price_date, end_price_date)
    asset_total = float(base["preco_acao"].iloc[-1] / base["preco_acao"].iloc[0] - 1)
    market_total = float(base["preco_mercado"].iloc[-1] / base["preco_mercado"].iloc[0] - 1)
    asset_annual = annualized_return(float(base["preco_acao"].iloc[0]), float(base["preco_acao"].iloc[-1]), years)
    market_annual = annualized_return(
        float(base["preco_mercado"].iloc[0]),
        float(base["preco_mercado"].iloc[-1]),
        years,
    )
    rf = float(base["rf_anual"].mean() / 100)
    rf_total = float(np.prod(base["fator_rf_mensal"]) - 1)
    capm_precise = rf + beta * (market_annual - rf)
    capm_academic = round(capm_precise, 3)
    recommendation, difference = classify_academic(asset_annual, capm_academic)
    return CapmMetrics(
        rf=rf,
        rf_total=rf_total,
        rm=market_annual,
        asset_annualized_return=asset_annual,
        market_annualized_return=market_annual,
        asset_total_return=asset_total,
        market_total_return=market_total,
        capm_precise=capm_precise,
        capm_academic=capm_academic,
        classification_value=capm_academic,
        difference=difference,
        recommendation=recommendation,
        years=years,
    )


def run_analysis(config: AnalysisConfig) -> AnalysisResult:
    start, end = validate_config(config)
    load_start = (start.to_period("M") - 1).start_time
    slug = safe_slug(config.slug or config.asset_name or config.ticker)
    asset = load_asset_prices(config, load_start, end)
    market = load_market_prices(config, load_start, end)
    asset_monthly = _monthly_asset_frame(asset)
    market_monthly = _monthly_price_frame(market, price_column="preco", renamed_column="preco_mercado")
    _validate_same_monthly_index(asset_monthly.index, market_monthly.index, label="ativo e mercado")
    dates = asset_monthly.index
    risk_free = load_risk_free(config, dates)
    monthly_base = build_monthly_base(
        asset_monthly,
        market_monthly,
        risk_free,
    )
    base = compute_return_base(monthly_base)
    regression = ols_excess_returns(base["excesso_ativo"], base["excesso_mercado"])
    diagnostic = covariance_beta(base["retorno_ativo"], base["retorno_mercado"])
    metrics = calculate_metrics(base, regression.beta)
    return AnalysisResult(
        config=config,
        slug=slug,
        base=base,
        monthly_price_base=monthly_base,
        regression=regression,
        covariance=diagnostic,
        metrics=metrics,
    )
