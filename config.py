import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "HIGH")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "deepseek-r1:7b")
USE_OFFLINE_MODE = os.getenv("USE_OFFLINE_MODE", "false").lower() in ("true", "1", "yes")

THRESHOLDS = {
    "delta_debtor_days_yoy_warning": 3.0,
    "margin_wedge_bps": 50.0,
    "residual_divergence_warning": 3.0,
    "cfo_to_op_profit_min": 0.70,
    "peer_spread_delta_days": 3.0
}

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TRACK_C_NIFTY50 = [
    "HINDUNILVR",
    "ITC",
    "NESTLEIND",
    "BRITANNIA",
    "TATACONSUM",
    "TITAN",
    "ASIANPAINT",
    "TRENT"
]

PEER_MAPPING = {
    "HINDUNILVR": ["DABUR", "MARICO", "GODREJCP"],
    "ITC": ["HINDUNILVR", "GODREJCP", "VBL"],
    "NESTLEIND": ["BRITANNIA", "TATACONSUM", "HINDUNILVR"],
    "BRITANNIA": ["NESTLEIND", "ITC", "DABUR"],
    "TATACONSUM": ["NESTLEIND", "DABUR", "MARICO"],
    "TITAN": ["KALYANKJIL", "SENCO"],
    "ASIANPAINT": ["BERGEPAINT", "KANSAINER"],
    "TRENT": ["DMART", "ABFRL"]
}
