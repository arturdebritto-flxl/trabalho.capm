from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from capm.config import AnalysisConfig, TickerWindow
from capm.returns import annual_rate_to_monthly
from capm.validation import (
    ensure_enough_observations,
    parse_datetime_column,
    parse_numeric_column,
    validate_no_duplicate_dates,
    validate_required_columns,
)


def _format_month_list(index: pd.DatetimeIndex, *, limit: int = 5) -> str:
    values = index.sort_values()
    if len(values) > limit:
        values = values[:limit]
    return ", ".join(value.strftime("%Y-%m-%d") for value in values)


def _validate_period_coverage(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp, *, label: str) -> None:
    if index.empty:
        raise ValueError(f"{label} retornou base vazia.")
    start_period = start.to_period("M")
    end_period = end.to_period("M")
    first_period = index.min().to_period("M")
    last_period = index.max().to_period("M")
    if first_period > start_period or last_period < end_period:
        raise ValueError(
            f"{label} nao cobriu o periodo mensal solicitado: "
            f"esperado de {start_period.start_time.strftime('%Y-%m-%d')} a {end_period.end_time.strftime('%Y-%m-%d')}, "
            f"disponivel de {index.min().strftime('%Y-%m-%d')} a {index.max().strftime('%Y-%m-%d')}."
        )


def _normalize_price_frame(frame: pd.DataFrame, *, ticker: str, label: str) -> pd.DataFrame:
    validate_required_columns(frame, ("Data", "preco"), label=label)
    frame = frame.copy()
    frame["Data"] = parse_datetime_column(frame, "Data", label=label)
    frame["preco"] = parse_numeric_column(frame, "preco", label=label, strictly_positive=True)
    validate_no_duplicate_dates(frame)
    cleaned = frame.loc[:, ["Data", "preco"]].sort_values("Data")
    cleaned["ticker"] = ticker
    ensure_enough_observations(cleaned, minimum=2, label=label)
    return cleaned.set_index("Data")


def _extract_yahoo_close(data: pd.DataFrame, ticker: str) -> pd.Series:
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            raise ValueError(f"Yahoo Finance retornou MultiIndex sem coluna 'Close' para {ticker}.")
        close = data.xs("Close", axis=1, level=0)
        if isinstance(close, pd.DataFrame):
            if ticker in close.columns:
                close = close[ticker]
            elif close.shape[1] == 1:
                close = close.iloc[:, 0]
            else:
                raise ValueError(
                    f"Yahoo Finance retornou MultiIndex ambigua para {ticker}; "
                    "nao foi possivel isolar a coluna de fechamento."
                )
    else:
        if "Close" not in data.columns:
            raise ValueError(f"Yahoo Finance nao retornou coluna 'Close' para {ticker}.")
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return pd.Series(close, name="preco")


def _normalize_risk_free_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    validate_required_columns(frame, ("Data", "rf_anual"), label=label)
    frame = frame.copy()
    frame["Data"] = parse_datetime_column(frame, "Data", label=label)
    frame["rf_anual"] = parse_numeric_column(frame, "rf_anual", label=label)
    validate_no_duplicate_dates(frame)
    cleaned = frame.loc[:, ["Data", "rf_anual"]].sort_values("Data")
    ensure_enough_observations(cleaned, minimum=1, label=label)
    return cleaned.set_index("Data")


def load_price_csv(path: Path, *, ticker: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "Close" in frame.columns and "preco" not in frame.columns:
        frame = frame.rename(columns={"Close": "preco"})
    if "preco" not in frame.columns:
        raise ValueError(f"CSV de precos sem coluna 'preco' ou 'Close': {path}")
    return _normalize_price_frame(frame, ticker=ticker, label=str(path))


def download_yahoo_close(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    import yfinance as yf

    try:
        data = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=False,
        )
    except Exception as exc:
        raise ValueError(f"Falha ao consultar Yahoo Finance para {ticker}: {exc}") from exc
    if data.empty:
        raise ValueError(f"Yahoo Finance retornou base vazia para {ticker}.")
    close = _extract_yahoo_close(data, ticker)
    frame = pd.DataFrame({"Data": close.index, "preco": close.to_numpy()})
    normalized = _normalize_price_frame(frame, ticker=ticker, label=f"Yahoo Finance para {ticker}")
    _validate_period_coverage(normalized.index, start, end, label=f"Yahoo Finance para {ticker}")
    return normalized


def load_cotahist(cotahist_dir: Path, ticker_history: Iterable[TickerWindow]) -> pd.DataFrame:
    tickers = {item.ticker for item in ticker_history if item.ticker}
    if not tickers:
        raise ValueError("COTAHIST exige ticker_history configurado.")
    rows: list[dict[str, object]] = []
    for path in sorted(cotahist_dir.glob("COTAHIST_A*.TXT")):
        with path.open("r", encoding="latin1", errors="ignore") as fh:
            for line in fh:
                ticker = line[12:24].strip()
                if ticker in tickers and line[:2] == "01":
                    date = pd.Timestamp(f"{line[2:6]}-{line[6:8]}-{line[8:10]}")
                    price = int(line[108:121]) / 100
                    rows.append({"Data": date, "preco": price, "ticker": ticker})
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("COTAHIST nao encontrou observacoes para os tickers configurados.")
    validate_no_duplicate_dates(frame.sort_values("Data"))
    return frame.sort_values("Data").set_index("Data")


def apply_ticker_history(frame: pd.DataFrame, config: AnalysisConfig) -> pd.DataFrame:
    if not config.ticker_history:
        frame = frame.copy()
        frame["ticker"] = config.ticker
        return frame
    parts = []
    for item in config.ticker_history:
        start = pd.Timestamp(item.start) if item.start else frame.index.min()
        end = pd.Timestamp(item.end) if item.end else frame.index.max()
        part = frame.loc[(frame.index >= start) & (frame.index <= end)].copy()
        part["ticker"] = item.ticker
        parts.append(part)
    combined = pd.concat(parts).sort_index()
    if combined.index.duplicated().any():
        duplicated = combined.index[combined.index.duplicated()].astype(str).tolist()
        raise ValueError("Mudanca de ticker gerou datas duplicadas: " + ", ".join(duplicated[:5]))
    missing = frame.index.difference(combined.index)
    if len(missing):
        raise ValueError("Mudanca de ticker deixou datas sem cobertura: " + _format_month_list(missing))
    return combined


def load_asset_prices(config: AnalysisConfig, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    source = config.price_source
    if source in {"csv", "offline"}:
        assert config.asset_prices_csv is not None
        frame = load_price_csv(config.asset_prices_csv, ticker=config.ticker)
    elif source == "yahoo":
        frame = download_yahoo_close(config.ticker, start, end)
    elif source == "b3":
        if config.b3_cotahist_dir is None:
            raise ValueError("b3_cotahist_dir e obrigatorio para fonte b3.")
        frame = load_cotahist(config.b3_cotahist_dir, config.ticker_history)
    else:
        raise ValueError(f"Fonte de precos invalida: {source}.")
    _validate_period_coverage(frame.index, start, end, label=f"Precos do ativo {config.ticker}")
    filtered = frame.loc[(frame.index >= start) & (frame.index <= end)]
    return apply_ticker_history(filtered, config)


def load_market_prices(config: AnalysisConfig, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if config.price_source in {"csv", "offline"}:
        assert config.market_prices_csv is not None
        frame = load_price_csv(config.market_prices_csv, ticker=config.market)
        _validate_period_coverage(frame.index, start, end, label=f"Precos do mercado {config.market}")
        return frame.loc[(frame.index >= start) & (frame.index <= end)]
    return download_yahoo_close(config.market, start, end).loc[lambda df: (df.index >= start) & (df.index <= end)]


def load_risk_free(config: AnalysisConfig, dates: pd.DatetimeIndex) -> pd.DataFrame:
    if config.risk_free_source == "csv":
        assert config.risk_free_csv is not None
        frame = _normalize_risk_free_frame(pd.read_csv(config.risk_free_csv), label=str(config.risk_free_csv))
        frame = frame.resample("ME").last()
        frame = frame.reindex(dates)
        if frame["rf_anual"].isna().any():
            missing = frame.index[frame["rf_anual"].isna()]
            raise ValueError(
                "CSV de taxa livre nao cobre todas as datas mensais solicitadas: "
                + _format_month_list(missing)
            )
    elif config.risk_free_source == "annual_constant":
        assert config.risk_free_annual_rate is not None
        frame = pd.DataFrame({"rf_anual": config.risk_free_annual_rate}, index=dates)
    elif config.risk_free_source == "bcb_sgs":
        from bcb import sgs

        raw = sgs.get({"rf_anual": config.bcb_series}, start=dates.min(), end=dates.max())
        if raw is None or raw.empty:
            raise ValueError(
                f"BCB SGS retornou base vazia para a serie {config.bcb_series} no periodo solicitado."
            )
        if isinstance(raw.columns, pd.MultiIndex):
            if "rf_anual" in raw.columns.get_level_values(0):
                frame = raw.xs("rf_anual", axis=1, level=0)
            elif "rf_anual" in raw.columns.get_level_values(-1):
                frame = raw.xs("rf_anual", axis=1, level=-1)
            elif raw.shape[1] == 1:
                frame = raw.iloc[:, [0]].copy()
                frame.columns = ["rf_anual"]
            else:
                raise ValueError("BCB SGS retornou MultiIndex inesperado para a taxa livre de risco.")
        else:
            frame = raw.copy()
            if "rf_anual" not in frame.columns:
                if frame.shape[1] == 1:
                    frame = frame.rename(columns={frame.columns[0]: "rf_anual"})
                else:
                    raise ValueError("BCB SGS nao retornou coluna 'rf_anual'.")
        _validate_period_coverage(frame.index, dates.min(), dates.max(), label="BCB SGS")
        frame = frame.resample("ME").last()
        frame = frame.reindex(dates)
        if frame["rf_anual"].isna().any():
            missing = frame.index[frame["rf_anual"].isna()]
            raise ValueError(
                "BCB SGS nao cobre todas as datas mensais solicitadas: " + _format_month_list(missing)
            )
    else:
        raise ValueError(f"Taxa livre de risco invalida: {config.risk_free_source}.")
    frame["rf_anual"] = parse_numeric_column(frame, "rf_anual", label="Taxa livre de risco")
    if (frame["rf_anual"] <= -100).any():
        raise ValueError("Taxa livre de risco anual deve ser maior que -100%.")
    frame["rf_mensal"] = annual_rate_to_monthly(frame["rf_anual"])
    frame["fator_rf_mensal"] = 1 + frame["rf_mensal"]
    return frame
