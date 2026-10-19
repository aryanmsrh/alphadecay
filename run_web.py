#!/usr/bin/env python3
import sys
import os
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from webapp.app import create_app


def main():
    parser = argparse.ArgumentParser(description="Alpha Decay Financial Research Web Application")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")), help="Port number")
    parser.add_argument("--debug", action="store_true", default=False, help="Enable Flask debug mode")
    parser.add_argument("--offline", action="store_true", default=False, help="Force offline mode using local Ollama model")

    args = parser.parse_args()

    if args.offline:
        config.USE_OFFLINE_MODE = True
        os.environ["USE_OFFLINE_MODE"] = "true"

    app = create_app()

    print("=" * 70)
    print("  Alpha Decay // Financial Research Engine")
    print("=" * 70)
    print(f"  • Web Dashboard URL:     http://{args.host}:{args.port}/")
    print(f"  • Primary Model:         {config.GEMINI_MODEL} ({'Configured' if config.GEMINI_API_KEY else 'API Key Missing'})")
    print(f"  • Local Fallback Model:  {config.OLLAMA_FALLBACK_MODEL} ({config.OLLAMA_BASE_URL})")
    print(f"  • Execution Mode:        {'OFFLINE (Local Ollama)' if config.USE_OFFLINE_MODE else 'ONLINE (Gemini First)'}")
    print("=" * 70)

    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )


if __name__ == "__main__":
    main()
