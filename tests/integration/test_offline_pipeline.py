from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from capm.config import load_config
from capm.exports import export_outputs
from capm.model import run_analysis

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_example_config_runs_offline_and_exports_excel_and_charts() -> None:
    config = load_config(ROOT / "configs" / "example.toml")
    output_dir = ROOT / ".tmp" / "test_outputs" / "example"
    config = config.__class__(**{**config.__dict__, "output_dir": output_dir})
    result = run_analysis(config)
    paths = export_outputs(result)
    assert result.config.ticker == "FICT3"
    assert len(result.base) == 12
    assert paths["analysis_xlsx"].exists()
    assert paths["result_xlsx"].exists()
    assert paths["data_xlsx"].exists()
    assert paths["returns_png"].exists()
    assert paths["regression_png"].exists()
    with zipfile.ZipFile(paths["analysis_xlsx"]) as workbook:
        workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    sheet_names = [sheet.attrib["name"] for sheet in workbook_xml.findall("main:sheets/main:sheet", namespace)]
    assert sheet_names == ["Resumo", "Base mensal", "Precos mensais"]
    exported_summary = pd.read_csv(paths["streamlit_summary"])
    exported_fact = pd.read_csv(paths["streamlit_fact"])
    exported_capm = exported_summary.loc[
        exported_summary["Indicador"] == "CAPM preciso anual",
        "ValorNumerico",
    ].iloc[0]
    assert exported_capm == pytest.approx(result.metrics.capm_precise)
    assert len(exported_fact) == len(result.base)
    assert exported_fact["PrecoAcao"].iloc[-1] == pytest.approx(result.base["preco_acao"].iloc[-1])


@pytest.mark.integration
def test_data_exports_are_deterministic_and_csv_uses_lf() -> None:
    config = load_config(ROOT / "configs" / "example.toml")
    output_dir = ROOT / ".tmp" / "test_outputs" / "deterministic_excel"
    config = config.__class__(**{**config.__dict__, "output_dir": output_dir})
    result = run_analysis(config)
    paths = export_outputs(result)
    data_keys = (
        "analysis_xlsx",
        "result_xlsx",
        "data_xlsx",
        "streamlit_fact",
        "streamlit_summary",
        "streamlit_methodology",
    )
    first_hashes = {
        key: hashlib.sha256(paths[key].read_bytes()).digest()
        for key in data_keys
    }
    stable_mtime_ns = 1_700_000_000_000_000_000
    for key in ("streamlit_fact", "streamlit_summary", "streamlit_methodology"):
        os.utime(paths[key], ns=(stable_mtime_ns, stable_mtime_ns))

    paths = export_outputs(result)

    assert {
        key: hashlib.sha256(paths[key].read_bytes()).digest()
        for key in data_keys
    } == first_hashes
    for key in ("streamlit_fact", "streamlit_summary", "streamlit_methodology"):
        assert b"\r\n" not in paths[key].read_bytes()
        assert paths[key].stat().st_mtime_ns == stable_mtime_ns


@pytest.mark.integration
def test_academic_embraer_config_is_separate_from_core() -> None:
    config = load_config(ROOT / "configs" / "embraer.toml")
    output_dir = ROOT / ".tmp" / "test_outputs" / "embraer"
    config = config.__class__(**{**config.__dict__, "output_dir": output_dir})
    result = run_analysis(config)
    metrics = result.metrics
    assert result.config.asset_name == "Embraer S.A."
    assert len(result.base) == 96
    assert "EMBR3" in set(result.base["ticker_acao"])
    assert "EMBJ3" in set(result.base["ticker_acao"])
    assert result.base.index.min().strftime("%Y-%m-%d") == "2018-01-31"
    assert result.base.index.max().strftime("%Y-%m-%d") == "2025-12-31"
    assert (result.base.index.max() - result.base.index.min()).days == 2891
    assert result.base["preco_acao"].iloc[0] == pytest.approx(20.020000457763672)
    assert result.base["preco_acao"].iloc[-1] == pytest.approx(88.5999984741211)
    assert result.base["preco_mercado"].iloc[0] == pytest.approx(84913.0)
    assert result.base["preco_mercado"].iloc[-1] == pytest.approx(161125.0)
    assert metrics.years == pytest.approx(7.920547945205479)
    assert metrics.asset_total_return == pytest.approx(3.4255742481645344)
    assert metrics.market_total_return == pytest.approx(0.8975304134820346)
    assert metrics.market_annualized_return == pytest.approx(0.08423247624736185)
    assert result.regression.beta == pytest.approx(0.4837907315345737)
    assert metrics.rf == pytest.approx(0.08841770833333333)
    assert metrics.rm == pytest.approx(0.08423247624736185)
    assert metrics.capm_precise == pytest.approx(0.08639293184081923)
    assert metrics.capm_academic == pytest.approx(0.086)
    assert metrics.asset_annualized_return == pytest.approx(0.20658015947689834)
    assert metrics.classification_value == pytest.approx(0.086)
    assert metrics.difference == pytest.approx(0.12058015947689835)
    assert metrics.recommendation == "Compra"


@pytest.mark.integration
def test_local_csv_pipeline_supports_generic_asset_and_export_stability() -> None:
    tmp = ROOT / ".tmp" / "test_outputs" / "local_csv_generic"
    tmp.mkdir(parents=True, exist_ok=True)
    asset_csv = tmp / "asset.csv"
    market_csv = tmp / "market.csv"
    rf_csv = tmp / "rf.csv"
    asset_csv.write_text(
        "Data,preco\n2023-12-31,95\n2024-01-31,100\n2024-02-29,110\n2024-03-31,121\n",
        encoding="utf-8",
    )
    market_csv.write_text(
        "Data,Close\n2023-12-31,190\n2024-01-31,200\n2024-02-29,210\n2024-03-31,231\n",
        encoding="utf-8",
    )
    rf_csv.write_text(
        "Data,rf_anual\n2023-12-31,12\n2024-01-31,12\n2024-02-29,12\n2024-03-31,12\n",
        encoding="utf-8",
    )
    config = load_config(ROOT / "configs" / "example.toml")
    config = config.__class__(
        **{
            **config.__dict__,
            "ticker": "XYZ3",
            "market": "SPX",
            "asset_name": "Outro Ativo",
            "price_source": "csv",
            "risk_free_source": "csv",
            "start": "2024-01-01",
            "end": "2024-03-31",
            "slug": "outro_ativo",
            "asset_prices_csv": asset_csv,
            "market_prices_csv": market_csv,
            "risk_free_csv": rf_csv,
            "output_dir": tmp / "out",
        },
    )
    result = run_analysis(config)
    assert result.config.asset_name == "Outro Ativo"
    assert result.slug == "outro_ativo"
    assert result.base["ticker_acao"].tolist() == ["XYZ3", "XYZ3", "XYZ3"]
    assert result.metrics.capm_precise == pytest.approx(
        result.metrics.rf + result.regression.beta * (result.metrics.rm - result.metrics.rf)
    )
    assert result.metrics.capm_academic == round(result.metrics.capm_precise, 3)
    paths = export_outputs(result)
    fact_first = paths["streamlit_fact"].read_bytes()
    summary_first = paths["streamlit_summary"].read_bytes()
    methodology_first = paths["streamlit_methodology"].read_bytes()
    paths = export_outputs(result)
    assert paths["streamlit_fact"].read_bytes() == fact_first
    assert paths["streamlit_summary"].read_bytes() == summary_first
    assert paths["streamlit_methodology"].read_bytes() == methodology_first
    assert b"\r\n" not in fact_first
    assert b"\r\n" not in summary_first
    assert b"\r\n" not in methodology_first


@pytest.mark.integration
def test_local_csv_pipeline_rejects_misaligned_and_duplicate_inputs() -> None:
    tmp = ROOT / ".tmp" / "test_outputs" / "local_csv_rejects"
    tmp.mkdir(parents=True, exist_ok=True)
    asset_csv = tmp / "asset_bad.csv"
    market_csv = tmp / "market_bad.csv"
    rf_csv = tmp / "rf_bad.csv"
    asset_csv.write_text(
        "Data,preco\n2024-01-31,100\n2024-01-31,101\n",
        encoding="utf-8",
    )
    market_csv.write_text(
        "Data,preco\n2024-01-31,200\n2024-03-31,220\n",
        encoding="utf-8",
    )
    rf_csv.write_text(
        "Data,rf_anual\n2024-01-31,12\n2024-02-29,12\n2024-03-31,12\n",
        encoding="utf-8",
    )
    config = load_config(ROOT / "configs" / "example.toml")
    config = config.__class__(
        **{
            **config.__dict__,
            "price_source": "csv",
            "risk_free_source": "csv",
            "start": "2024-01-01",
            "end": "2024-03-31",
            "asset_prices_csv": asset_csv,
            "market_prices_csv": market_csv,
            "risk_free_csv": rf_csv,
            "output_dir": tmp / "out",
        },
    )
    with pytest.raises(ValueError, match="Datas duplicadas"):
        run_analysis(config)

    asset_csv.write_text(
        "Data,preco\n2023-12-31,95\n2024-01-31,100\n2024-02-29,110\n2024-03-31,120\n",
        encoding="utf-8",
    )
    market_csv.write_text(
        "Data,preco\n2023-12-31,190\n2024-01-31,200\n2024-03-31,220\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Desalinhamento mensal"):
        run_analysis(config)


@pytest.mark.integration
def test_embraer_complete_flow_exports_all_expected_artifacts() -> None:
    config = load_config(ROOT / "configs" / "embraer.toml")
    output_dir = ROOT / ".tmp" / "test_outputs" / "embraer_complete"
    config = config.__class__(**{**config.__dict__, "output_dir": output_dir})
    result = run_analysis(config)
    paths = export_outputs(result)
    assert result.config.asset_name == "Embraer S.A."
    assert result.base.index.min().strftime("%Y-%m-%d") == "2018-01-31"
    assert result.base.index.max().strftime("%Y-%m-%d") == "2025-12-31"
    assert result.metrics.recommendation == "Compra"
    assert all(path.exists() and path.stat().st_size > 0 for path in paths.values())
