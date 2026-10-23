import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")

DEFAULT_PROVIDER = "gemini"

OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "600.0"))
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "90.0"))

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
    "TRENT",
]

PEER_MAPPING = {
    "HINDUNILVR": ["DABUR", "MARICO", "GODREJCP"],
    "ITC": ["HINDUNILVR", "GODREJCP", "VBL"],
    "NESTLEIND": ["BRITANNIA", "TATACONSUM", "HINDUNILVR"],
    "BRITANNIA": ["NESTLEIND", "ITC", "DABUR"],
    "TATACONSUM": ["NESTLEIND", "DABUR", "MARICO"],
    "TITAN": ["KALYANKJIL", "SENCO"],
    "ASIANPAINT": ["BERGEPAINT", "KANSAINER"],
    "TRENT": ["DMART", "ABFRL"],
}
