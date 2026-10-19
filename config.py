import os
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- API Keys & Remote Endpoints ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "HIGH")

# --- Local Ollama Configuration (Fallback Only) ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", os.getenv("LOCAL_MODEL", "deepseek-r1:7b"))
LOCAL_MODEL = OLLAMA_FALLBACK_MODEL  # Backwards compatibility alias

# --- Operational Toggles ---
# Offline Failsafe Switch: If True, bypasses cloud calls and routes to Ollama
USE_OFFLINE_MODE = os.getenv("USE_OFFLINE_MODE", "false").lower() in ("true", "1", "yes")

# Reproducible Investigation Cutoff Date (YYYY-MM-DD); empty means no cutoff
INVESTIGATION_CUTOFF_DATE = os.getenv("INVESTIGATION_CUTOFF_DATE", "")

# Investigation Limits
MAX_ANOMALIES_TO_INVESTIGATE = int(os.getenv("MAX_ANOMALIES_TO_INVESTIGATE", "2"))

# --- Track C Universe (NIFTY 50 FMCG / Consumer / Retail) ---
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

# Direct Listed Peers for Triangulation & Comparative Context
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

# --- Forensic Anomaly Screening Thresholds (Documented Heuristics) ---
# Note: These represent screening trigger boundaries, not statistical proofs of misconduct.
THRESHOLDS = {
    # Working Capital: debtor days widening YoY
    "delta_debtor_days_yoy_warning": float(os.getenv("THRESH_DEBTOR_DAYS", "3.0")),
    # Cash Conversion: CFO / Operating Profit benchmark
    "cfo_to_op_profit_min": float(os.getenv("THRESH_CFO_CONV", "0.70")),
    "cfo_to_ebitda_min": float(os.getenv("THRESH_CFO_CONV", "0.70")),  # Compatibility alias
    # Heuristic Cost Residual Divergence: reported sales growth minus expense-adjusted residual
    "residual_divergence_warning": float(os.getenv("THRESH_RESIDUAL_DIV", "3.0")),
    # Operating Margin Compression / Wedge
    "margin_wedge_bps": float(os.getenv("THRESH_MARGIN_WEDGE", "50.0")),
    # Multi-Peer Spread: Target metric shift vs Peer median shift
    "peer_spread_delta_days": float(os.getenv("THRESH_PEER_SPREAD", "3.0"))
}
