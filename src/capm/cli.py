from __future__ import annotations

import argparse
import logging
from pathlib import Path

from capm.config import AnalysisConfig, config_from_mapping, load_config
from capm.exports import export_outputs
from capm.model import run_analysis


def format_percent(value: float) -> str:
    return f"{value:.2%}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executa uma analise CAPM generica.")
    parser.add_argument("--config", type=Path, help="Arquivo TOML de configuracao.")
    parser.add_argument("--ticker", help="Ticker do ativo.")
    parser.add_argument("--market", help="Ticker do mercado.")
    parser.add_argument("--start", help="Data inicial YYYY-MM-DD.")
    parser.add_argument("--end", help="Data final YYYY-MM-DD.")
    parser.add_argument("--source", choices=["offline", "csv", "yahoo", "b3"], default=None)
    parser.add_argument("--risk-free-source", choices=["csv", "annual_constant", "bcb_sgs"], default=None)
    parser.add_argument("--asset-prices-csv", type=Path)
    parser.add_argument("--market-prices-csv", type=Path)
    parser.add_argument("--risk-free-csv", type=Path)
    parser.add_argument("--risk-free-annual-rate", type=float)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--slug")
    parser.add_argument("--offline", action="store_true", help="Forca fonte offline/CSV configurada.")
    parser.add_argument("--yes", action="store_true", help="Executa sem confirmacao.")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def configure_logging(args: argparse.Namespace) -> None:
    level = logging.WARNING if args.quiet else logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s - %(message)s")


def config_from_args(args: argparse.Namespace) -> AnalysisConfig:
    if args.config:
        config = load_config(args.config)
        data = config.__dict__.copy()
        if args.offline:
            data["price_source"] = "offline"
        overrides = {
            "ticker": args.ticker,
            "market": args.market,
            "start": args.start,
            "end": args.end,
            "price_source": args.source,
            "risk_free_source": args.risk_free_source,
            "asset_prices_csv": args.asset_prices_csv,
            "market_prices_csv": args.market_prices_csv,
            "risk_free_csv": args.risk_free_csv,
            "risk_free_annual_rate": args.risk_free_annual_rate,
            "output_dir": args.output_dir,
            "slug": args.slug,
        }
        for key, value in overrides.items():
            if value is not None:
                data[key] = value
        return AnalysisConfig(**data)

    required = {"ticker": args.ticker, "market": args.market, "start": args.start, "end": args.end}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("Argumentos obrigatorios sem --config: " + ", ".join(missing))

    source = "offline" if args.offline else args.source or "yahoo"
    risk_source = args.risk_free_source or ("csv" if args.risk_free_csv else "annual_constant")
    return config_from_mapping(
        {
            "ticker": args.ticker,
            "market": args.market,
            "start": args.start,
            "end": args.end,
            "price_source": source,
            "risk_free_source": risk_source,
            "asset_prices_csv": args.asset_prices_csv,
            "market_prices_csv": args.market_prices_csv,
            "risk_free_csv": args.risk_free_csv,
            "risk_free_annual_rate": args.risk_free_annual_rate if args.risk_free_annual_rate is not None else 10.0,
            "output_dir": args.output_dir or "dados",
            "slug": args.slug,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args)
    config = config_from_args(args)
    if not args.yes:
        answer = input("A analise gerara/atualizara arquivos de saida. Continuar? [s/N]: ").strip().lower()
        if answer not in {"s", "sim"}:
            print("Execucao cancelada.")
            return 1
    result = run_analysis(config)
    paths = export_outputs(result)
    print("\nRESULTADOS PRINCIPAIS")
    print(f"Ativo: {config.asset_name or config.ticker}")
    print(f"Ticker: {config.ticker}")
    print(f"Mercado: {config.market}")
    print(f"Observacoes mensais: {len(result.base)}")
    print(f"Beta OLS usado no CAPM: {result.regression.beta:.4f}")
    print(f"Alfa: {result.regression.alpha:.4f}")
    print(f"R2: {result.regression.r_squared:.4f}")
    print(f"CAPM preciso: {format_percent(result.metrics.capm_precise)} ao ano")
    print(f"CAPM arredondado academico: {format_percent(result.metrics.capm_academic)} ao ano")
    print(f"Classificacao academica: {result.metrics.recommendation}")
    print(f"Aviso: {config.presentation.disclaimer}")
    print(f"Excel principal: {paths['analysis_xlsx']}")
    print(f"Grafico de retornos: {paths['returns_png']}")
    print(f"Grafico de regressao: {paths['regression_png']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
