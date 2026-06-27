from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm


@dataclass(frozen=True)
class RegressionResult:
    alpha: float
    beta: float
    r_squared: float


@dataclass(frozen=True)
class CovarianceDiagnostic:
    beta: float
    covariance: float
    market_variance: float


def ols_excess_returns(excess_asset: pd.Series, excess_market: pd.Series) -> RegressionResult:
    y, x = excess_asset.align(excess_market, join="inner")
    frame = pd.DataFrame({"asset": y, "market": x}).dropna()
    if len(frame) < 2:
        raise ValueError("A regressao OLS exige pelo menos duas observacoes.")
    if np.isclose(frame["market"].var(), 0.0):
        raise ValueError("A variancia do mercado e zero; beta nao pode ser estimado.")
    model_x = sm.add_constant(frame["market"], has_constant="add")
    fit = sm.OLS(frame["asset"], model_x).fit()
    return RegressionResult(
        alpha=float(fit.params["const"]),
        beta=float(fit.params["market"]),
        r_squared=float(fit.rsquared),
    )


def covariance_beta(asset_returns: pd.Series, market_returns: pd.Series) -> CovarianceDiagnostic:
    y, x = asset_returns.align(market_returns, join="inner")
    frame = pd.DataFrame({"asset": y, "market": x}).dropna()
    variance = float(frame["market"].var())
    if np.isclose(variance, 0.0):
        raise ValueError("Variancia do mercado igual a zero.")
    covariance = float(frame["asset"].cov(frame["market"]))
    return CovarianceDiagnostic(
        beta=covariance / variance,
        covariance=covariance,
        market_variance=variance,
    )
