from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from capm.data_sources import load_price_csv
from capm.model import calculate_metrics, classify_academic, compute_return_base
from capm.regression import covariance_beta, ols_excess_returns
from capm.returns import annual_rate_to_monthly, annualized_return, monthly_prices, years_between
from capm.validation import ensure_enough_observations, parse_date, safe_slug

ROOT = Path(__file__).resolve().parents[2]


def test_annual_rate_to_monthly() -> None:
    assert annual_rate_to_monthly(12.0) == pytest.approx((1 + 12.0 / 100) ** (1 / 12) - 1)


def test_monthly_prices_uses_month_end_last_observation() -> None:
    prices = pd.DataFrame(
        {"preco": [10.0, 11.0, 12.0, 13.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-31", "2024-02-01", "2024-02-29"]),
    )
    monthly = monthly_prices(prices)
    assert monthly.loc[pd.Timestamp("2024-01-31"), "preco"] == 11.0
    assert monthly.loc[pd.Timestamp("2024-02-29"), "preco"] == 13.0


def test_compute_return_base_uses_pct_change_and_excess_returns() -> None:
    base = pd.DataFrame(
        {
            "preco_acao": [100.0, 110.0, 121.0],
            "preco_mercado": [200.0, 210.0, 231.0],
            "ticker_acao": ["AAA", "AAA", "AAA"],
            "rf_anual": [12.0, 12.0, 12.0],
            "rf_mensal": [0.01, 0.01, 0.01],
            "fator_rf_mensal": [1.01, 1.01, 1.01],
        },
        index=pd.date_range("2024-01-31", periods=3, freq="ME"),
    )
    result = compute_return_base(base)
    assert result["retorno_ativo"].to_list() == pytest.approx([0.10, 0.10])
    assert result["retorno_mercado"].to_list() == pytest.approx([0.05, 0.10])
    assert result["excesso_ativo"].to_list() == pytest.approx([0.09, 0.09])
    assert result["excesso_mercado"].to_list() == pytest.approx([0.04, 0.09])


def test_ols_with_constant_recovers_alpha_beta() -> None:
    market = pd.Series([-0.02, 0.00, 0.01, 0.03, 0.05])
    asset = 0.01 + 1.5 * market
    result = ols_excess_returns(asset, market)
    assert result.alpha == pytest.approx(0.01)
    assert result.beta == pytest.approx(1.5)
    assert result.r_squared == pytest.approx(1.0)


def test_covariance_beta_is_diagnostic_formula() -> None:
    market = pd.Series([0.01, 0.02, 0.03, 0.04])
    asset = pd.Series([0.02, 0.04, 0.06, 0.08])
    result = covariance_beta(asset, market)
    assert result.beta == pytest.approx(2.0)
    assert result.covariance == pytest.approx(asset.cov(market))
    assert result.market_variance == pytest.approx(market.var())


def test_years_and_annualized_return_use_effective_dates() -> None:
    years = years_between(pd.Timestamp("2024-01-31"), pd.Timestamp("2025-01-31"))
    assert years == pytest.approx(366 / 365)
    assert annualized_return(100.0, 121.0, years) == pytest.approx((1.21) ** (1 / years) - 1)


def test_calculate_metrics_preserves_precise_and_academic_capm() -> None:
    index = pd.date_range("2024-01-31", periods=4, freq="ME")
    base = pd.DataFrame(
        {
            "preco_acao": [100.0, 106.0, 112.0, 120.0],
            "preco_mercado": [1000.0, 1020.0, 1040.0, 1080.0],
            "rf_anual": [10.0, 10.0, 10.0, 10.0],
            "fator_rf_mensal": [1.008] * 4,
        },
        index=index,
    )
    metrics = calculate_metrics(base, beta=1.2)
    expected = metrics.rf + 1.2 * (metrics.rm - metrics.rf)
    assert metrics.capm_precise == pytest.approx(expected)
    assert metrics.capm_academic == round(metrics.capm_precise, 3)
    assert metrics.classification_value == metrics.capm_academic


def test_classification_uses_academic_rounded_value() -> None:
    recommendation, difference = classify_academic(asset_return=0.1004, capm_academic=0.100)
    assert recommendation == "Compra"
    assert difference == pytest.approx(0.0004)
    recommendation, difference = classify_academic(asset_return=0.1000, capm_academic=0.100)
    assert recommendation == "Manutencao"
    assert difference == pytest.approx(0.0)
    recommendation, difference = classify_academic(asset_return=0.095, capm_academic=0.100)
    assert recommendation == "Venda"
    assert difference == pytest.approx(-0.005)


def test_ols_rejects_zero_market_variance() -> None:
    with pytest.raises(ValueError, match="variancia"):
        ols_excess_returns(pd.Series([0.1, 0.2, 0.3]), pd.Series([0.01, 0.01, 0.01]))


def test_returns_and_validation_reject_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="Periodo insuficiente"):
        years_between(pd.Timestamp("2024-01-31"), pd.Timestamp("2024-01-31"))
    with pytest.raises(ValueError, match="Precos devem ser positivos"):
        annualized_return(100.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="Slug vazio"):
        safe_slug("///")
    with pytest.raises(ValueError, match="Data invalida"):
        parse_date("2024-02-30", "start")
    with pytest.raises(ValueError, match="Numero insuficiente"):
        ensure_enough_observations(pd.DataFrame({"x": [1]}), minimum=2, label="x")


def test_validate_no_duplicate_dates_and_load_price_csv() -> None:
    workdir = ROOT / ".tmp" / "test_outputs" / "unit_math"
    workdir.mkdir(parents=True, exist_ok=True)
    csv_path = workdir / "precos.csv"
    csv_path.write_text("Data,Close\n2024-01-31,10\n2024-01-31,11\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Datas duplicadas"):
        load_price_csv(csv_path, ticker="AAA")

    csv_path.write_text("Data,preco\n2024-01-31,10\n2024-02-29,\n2024-03-31,12\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nulos"):
        load_price_csv(csv_path, ticker="AAA")

    csv_path.write_text("Data,preco\n2024-01-31,10\n2024-02-29,inf\n", encoding="utf-8")
    with pytest.raises(ValueError, match="infinitos"):
        load_price_csv(csv_path, ticker="AAA")


def test_compute_return_base_rejects_infinities() -> None:
    base = pd.DataFrame(
        {
            "preco_acao": [100.0, float("inf"), 121.0],
            "preco_mercado": [200.0, 210.0, 231.0],
            "ticker_acao": ["AAA", "AAA", "AAA"],
            "rf_anual": [12.0, 12.0, 12.0],
            "rf_mensal": [0.01, 0.01, 0.01],
            "fator_rf_mensal": [1.01, 1.01, 1.01],
        },
        index=pd.date_range("2024-01-31", periods=3, freq="ME"),
    )
    with pytest.raises(ValueError, match="infinitos"):
        compute_return_base(base)
