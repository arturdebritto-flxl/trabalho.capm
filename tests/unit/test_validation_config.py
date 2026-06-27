from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from capm.config import TickerWindow, config_from_mapping
from capm.data_sources import apply_ticker_history
from capm.validation import safe_slug, validate_config


def test_safe_slug_blocks_path_like_values() -> None:
    assert safe_slug("PETR4.SA") == "petr4_sa"
    assert safe_slug("analise capm ativo") == "analise_capm_ativo"
    with pytest.raises(ValueError):
        safe_slug("///")


def test_validate_config_rejects_empty_ticker_and_bad_dates() -> None:
    config = config_from_mapping(
        {
            "ticker": "",
            "market": "MKT",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "asset_prices_csv": "a.csv",
            "market_prices_csv": "m.csv",
            "risk_free_csv": "rf.csv",
        },
        base_dir=Path.cwd(),
    )
    with pytest.raises(ValueError, match="Ticker"):
        validate_config(config)

    config = config_from_mapping(
        {
            "ticker": "AAA",
            "market": "MKT",
            "start": "2025-01-01",
            "end": "2024-12-31",
            "asset_prices_csv": "a.csv",
            "market_prices_csv": "m.csv",
            "risk_free_csv": "rf.csv",
        },
        base_dir=Path.cwd(),
    )
    with pytest.raises(ValueError, match="posterior"):
        validate_config(config)


def test_apply_ticker_history_is_generic() -> None:
    frame = pd.DataFrame(
        {"preco": [10.0, 11.0, 12.0]},
        index=pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"]),
    )
    config = config_from_mapping(
        {
            "ticker": "BBB",
            "market": "MKT",
            "start": "2024-01-01",
            "end": "2024-03-31",
            "asset_prices_csv": "a.csv",
            "market_prices_csv": "m.csv",
            "risk_free_csv": "rf.csv",
        },
        base_dir=Path.cwd(),
    )
    object.__setattr__(
        config,
        "ticker_history",
        (TickerWindow("AAA", end="2024-02-29"), TickerWindow("BBB", start="2024-03-01")),
    )
    result = apply_ticker_history(frame, config)
    assert result["ticker"].to_list() == ["AAA", "AAA", "BBB"]
