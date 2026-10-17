import os
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- API Keys & Remote Endpoints ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Local Ollama Configuration ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Unified Local Model (DeepSeek-R1-7B fits 100% inside 8GB VRAM with ~3.2 GB context headroom)
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-r1:7b")

# --- Operational Toggles ---
# Offline Failsafe Switch: If True, bypasses all cloud calls (Gemini/Tavily) and runs 100% locally
USE_OFFLINE_MODE = os.getenv("USE_OFFLINE_MODE", "false").lower() in ("true", "1", "yes")

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

# Direct Listed Peers for Triangulation & Tie-Breaks
PEER_MAPPING = {
    "HINDUNILVR": ["DABUR", "MARICO", "GODREJCP"],
    "ITC": ["HINDUNILVR", "GODREJCP", "VBL"],
    "NESTLEIND": ["BRITANNIA", "TATACONSUM", "HINDUNILVR"],
    "BRITANNIA": ["NESTLEIND", "ITC", "PARLE"],
    "TATACONSUM": ["NESTLEIND", "DABUR", "MARICO"],
    "TITAN": ["KALYANKJIL", "SENCO"],
    "ASIANPAINT": ["BERGEPAINT", "KANSAINER"],
    "TRENT": ["DMART", "ABFRL"]
}

# --- Forensic Anomaly Thresholds ---
THRESHOLDS = {
    "delta_debtor_days_yoy_warning": 15.0,  # Spiking >= 15 days is high priority
    "cfo_to_ebitda_min": 0.65,              # Below 65% indicates paper profit
    "uvg_consecutive_negative_quarters": 2, # Volume contraction for 2+ quarters
    "margin_wedge_bps": 150.0,              # >150 bps gross vs ebitda wedge (Quick Commerce drag)
    "peer_spread_delta_days": 15.0          # Company debtor days stretch vs peer median
}
