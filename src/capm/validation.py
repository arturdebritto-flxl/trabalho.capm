from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from capm.config import AnalysisConfig, TickerWindow

VALID_PRICE_SOURCES = {"offline", "csv", "yahoo", "b3"}
VALID_RISK_FREE_SOURCES = {"csv", "annual_constant", "bcb_sgs"}
VALID_ANNUALIZATION_METHODS = {"calendar_days"}


def parse_date(value: str, field_name: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except Exception as exc:
        raise ValueError(f"Data invalida em {field_name}: {value!r}. Use YYYY-MM-DD.") from exc
    if pd.isna(parsed):
        raise ValueError(f"Data invalida em {field_name}: {value!r}.")
    return parsed.normalize()


def safe_slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        raise ValueError("Slug vazio apos sanitizacao.")
    if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
        raise ValueError("Slug invalido.")
    return normalized[:80]


def ensure_enough_observations(frame: pd.DataFrame, *, minimum: int, label: str) -> None:
    if frame.empty:
        raise ValueError(f"Base vazia: {label}.")
    if len(frame) < minimum:
        raise ValueError(
            f"Numero insuficiente de observacoes em {label}: "
            f"{len(frame)} encontrado(s), minimo {minimum}."
        )


def validate_required_columns(frame: pd.DataFrame, required_columns: Iterable[str], *, label: str) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} sem coluna(s) obrigatoria(s): {', '.join(missing)}.")


def parse_datetime_column(frame: pd.DataFrame, date_column: str, *, label: str) -> pd.Series:
    values = pd.to_datetime(frame[date_column], errors="coerce")
    invalid = values.isna()
    if invalid.any():
        samples = [str(value) for value in frame.loc[invalid, date_column].tolist()]
        raise ValueError(
            f"{label} possui datas invalidas na coluna {date_column}: "
            + ", ".join(samples[:5])
        )
    return values.dt.normalize()


def parse_numeric_column(
    frame: pd.DataFrame,
    column: str,
    *,
    label: str,
    strictly_positive: bool = False,
) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    invalid = values.isna() | ~np.isfinite(values)
    if invalid.any():
        samples = [str(value) for value in frame.loc[invalid, column].tolist()]
        raise ValueError(
            f"{label} possui valores nulos, invalidos ou infinitos na coluna {column}: "
            + ", ".join(samples[:5])
        )
    if strictly_positive and (values <= 0).any():
        samples = [str(value) for value in frame.loc[values <= 0, column].tolist()]
        raise ValueError(
            f"{label} possui valores nao positivos na coluna {column}: "
            + ", ".join(samples[:5])
        )
    return values


def validate_no_duplicate_dates(frame: pd.DataFrame, date_column: str = "Data") -> None:
    duplicated = frame[date_column].duplicated()
    if duplicated.any():
        values = frame.loc[duplicated, date_column].astype(str).tolist()
        raise ValueError("Datas duplicadas encontradas: " + ", ".join(values[:5]))


def validate_ticker_history(windows: tuple[TickerWindow, ...], start: pd.Timestamp, end: pd.Timestamp) -> None:
    for item in windows:
        if not item.ticker:
            raise ValueError("Mudanca de ticker inconsistente: ticker vazio.")
        item_start = parse_date(item.start, "ticker_history.start") if item.start else start
        item_end = parse_date(item.end, "ticker_history.end") if item.end else end
        if item_start > item_end:
            raise ValueError(f"Mudanca de ticker inconsistente para {item.ticker}: inicio apos fim.")


def validate_config(config: AnalysisConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    if not config.ticker:
        raise ValueError("Ticker do ativo vazio.")
    if not config.market:
        raise ValueError("Ticker de mercado ausente.")
    start = parse_date(config.start, "start")
    end = parse_date(config.end, "end")
    if start > end:
        raise ValueError("Data inicial posterior a data final.")
    if config.price_source not in VALID_PRICE_SOURCES:
        raise ValueError(f"Fonte de precos invalida: {config.price_source}.")
    if config.risk_free_source not in VALID_RISK_FREE_SOURCES:
        raise ValueError(f"Taxa livre de risco invalida: {config.risk_free_source}.")
    if config.frequency != "monthly":
        raise ValueError("Apenas frequencia mensal e suportada nesta versao.")
    if config.annualization_method not in VALID_ANNUALIZATION_METHODS:
        raise ValueError(f"Metodo de anualizacao invalido: {config.annualization_method}.")
    if config.price_source in {"csv", "offline"}:
        _require_path(config.asset_prices_csv, "asset_prices_csv")
        _require_path(config.market_prices_csv, "market_prices_csv")
    if config.risk_free_source == "csv":
        _require_path(config.risk_free_csv, "risk_free_csv")
    if config.risk_free_source == "annual_constant" and config.risk_free_annual_rate is None:
        raise ValueError("risk_free_annual_rate e obrigatorio para annual_constant.")
    if config.risk_free_source == "annual_constant":
        rate = float(config.risk_free_annual_rate)
        if not np.isfinite(rate) or rate <= -100:
            raise ValueError("risk_free_annual_rate deve ser finita e maior que -100%.")
    if config.price_source == "b3":
        if config.b3_cotahist_dir is None or not config.b3_cotahist_dir.is_dir():
            raise ValueError("b3_cotahist_dir deve indicar um diretorio existente.")
    validate_ticker_history(config.ticker_history, start, end)
    return start, end


def _require_path(path: Path | None, field_name: str) -> None:
    if path is None:
        raise ValueError(f"{field_name} e obrigatorio para esta fonte.")
    if not path.is_file():
        raise ValueError(f"{field_name} nao encontrado ou nao e arquivo: {path}")
