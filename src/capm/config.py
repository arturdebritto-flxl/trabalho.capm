from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TickerWindow:
    ticker: str
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class PresentationConfig:
    title: str = "Analise CAPM"
    academic_classification: bool = True
    disclaimer: str = (
        "Classificacao academica para fins educacionais; nao constitui "
        "recomendacao financeira profissional."
    )


@dataclass(frozen=True)
class AnalysisConfig:
    ticker: str
    market: str
    start: str
    end: str
    asset_name: str | None = None
    price_source: str = "offline"
    risk_free_source: str = "csv"
    frequency: str = "monthly"
    annualization_method: str = "calendar_days"
    output_dir: Path = Path("dados")
    slug: str | None = None
    asset_prices_csv: Path | None = None
    market_prices_csv: Path | None = None
    risk_free_csv: Path | None = None
    risk_free_annual_rate: float | None = None
    bcb_series: int = 4389
    b3_cotahist_dir: Path | None = None
    ticker_history: tuple[TickerWindow, ...] = field(default_factory=tuple)
    presentation: PresentationConfig = field(default_factory=PresentationConfig)


def _path_or_none(value: Any, base_dir: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else (base_dir / path).resolve()


def _ticker_history(raw: list[dict[str, Any]] | None) -> tuple[TickerWindow, ...]:
    if not raw:
        return ()
    return tuple(
        TickerWindow(
            ticker=str(item.get("ticker", "")).strip(),
            start=item.get("start"),
            end=item.get("end"),
        )
        for item in raw
    )


def config_from_mapping(data: dict[str, Any], *, base_dir: Path | None = None) -> AnalysisConfig:
    base = base_dir or Path.cwd()
    presentation_data = data.get("presentation", {}) or {}
    return AnalysisConfig(
        asset_name=data.get("asset_name") or data.get("name"),
        ticker=str(data.get("ticker", "")).strip(),
        market=str(data.get("market", "")).strip(),
        start=str(data.get("start", "")).strip(),
        end=str(data.get("end", "")).strip(),
        price_source=str(data.get("price_source", "offline")).strip().lower(),
        risk_free_source=str(data.get("risk_free_source", "csv")).strip().lower(),
        frequency=str(data.get("frequency", "monthly")).strip().lower(),
        annualization_method=str(data.get("annualization_method", "calendar_days")).strip().lower(),
        output_dir=_path_or_none(data.get("output_dir", "dados"), base) or Path("dados"),
        slug=data.get("slug"),
        asset_prices_csv=_path_or_none(data.get("asset_prices_csv"), base),
        market_prices_csv=_path_or_none(data.get("market_prices_csv"), base),
        risk_free_csv=_path_or_none(data.get("risk_free_csv"), base),
        risk_free_annual_rate=data.get("risk_free_annual_rate"),
        bcb_series=int(data.get("bcb_series", 4389)),
        b3_cotahist_dir=_path_or_none(data.get("b3_cotahist_dir"), base),
        ticker_history=_ticker_history(data.get("ticker_history")),
        presentation=PresentationConfig(
            title=str(presentation_data.get("title", "Analise CAPM")),
            academic_classification=bool(presentation_data.get("academic_classification", True)),
            disclaimer=str(
                presentation_data.get(
                    "disclaimer",
                    PresentationConfig.disclaimer,
                )
            ),
        ),
    )


def load_config(path: str | Path) -> AnalysisConfig:
    config_path = Path(path).resolve()
    with config_path.open("rb") as fh:
        data = tomllib.load(fh)
    return config_from_mapping(data, base_dir=config_path.parent)
