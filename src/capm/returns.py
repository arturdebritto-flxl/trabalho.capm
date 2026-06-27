from __future__ import annotations

import pandas as pd


def annual_rate_to_monthly(rf_anual_percent: pd.Series | float) -> pd.Series | float:
    return (1 + rf_anual_percent / 100) ** (1 / 12) - 1


def monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("O indice de precos deve ser DatetimeIndex.")
    return prices.sort_index().resample("ME").last()


def percent_returns(series: pd.Series) -> pd.Series:
    return series.pct_change()


def excess_returns(returns: pd.Series, rf_monthly: pd.Series) -> pd.Series:
    aligned_returns, aligned_rf = returns.align(rf_monthly, join="inner")
    return aligned_returns - aligned_rf


def years_between(start: pd.Timestamp, end: pd.Timestamp) -> float:
    days = (end - start).days
    if days <= 0:
        raise ValueError("Periodo insuficiente para anualizacao.")
    return days / 365


def annualized_return(initial_price: float, final_price: float, years: float) -> float:
    if initial_price <= 0 or final_price <= 0:
        raise ValueError("Precos devem ser positivos para anualizacao.")
    if years <= 0:
        raise ValueError("Periodo em anos deve ser positivo.")
    total = final_price / initial_price - 1
    return (1 + total) ** (1 / years) - 1
