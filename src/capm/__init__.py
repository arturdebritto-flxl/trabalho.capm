"""Generic CAPM analysis toolkit."""

from capm.config import AnalysisConfig, TickerWindow, load_config
from capm.model import AnalysisResult, run_analysis

__all__ = [
    "AnalysisConfig",
    "AnalysisResult",
    "TickerWindow",
    "load_config",
    "run_analysis",
]
