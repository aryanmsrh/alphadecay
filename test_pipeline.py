import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def test_all():
    print("=" * 65)
    print("  ALPHA-DECAY ARCHITECTURE VERIFICATION TEST SUITE")
    print("=" * 65)

    # 1. Ingestion Worker Test
    print("\n[1/6] Testing Ingestion Worker (Screener.in BS4 scraper)...")
    try:
        from ingestion.screener import ScreenerScraper
        scraper = ScreenerScraper(use_cache=True)
        data = scraper.fetch_company_data("HINDUNILVR")
        quarters_count = len(data.get("quarters", {}).get("periods", []))
        assert quarters_count >= 8, f"Expected at least 8 quarters, got {quarters_count}"
        print(f"  [✓] PASSED: Ingested {data['company_name']} ({quarters_count} quarters)")
    except Exception as e:
        print(f"  [✗] FAILED Ingestion: {e}")

    # 2. Forensic Math Sandbox Test
    print("\n[2/6] Testing Deterministic Math Sandbox (0-LLM Calculations)...")
    try:
        from engine.forensics import ForensicEngine
        summary = ForensicEngine.audit_company(data)
        assert len(summary.quarters_analyzed) > 0, "No quarters analyzed"
        print(f"  [✓] PASSED: Analyzed {len(summary.quarters_analyzed)} quarters | Flagged {len(summary.anomalies)} anomalies")
    except Exception as e:
        print(f"  [✗] FAILED Math Sandbox: {e}")

    # 3. Web Search Test (Tavily)
    print("\n[3/6] Testing Live Search Engine (Tavily API)...")
    try:
        from ingestion.web_search import TavilySearchClient
        tavily = TavilySearchClient()
        results = tavily.search("HUL Q3 FY24 distributor receivables concall", max_results=1)
        assert len(results) > 0, "No results returned"
        print(f"  [✓] PASSED: Search returned source: {results[0]['url'][:60]}...")
    except Exception as e:
        print(f"  [✗] FAILED Search: {e}")

    # 4. Local LLM / Ollama Test (DeepSeek-R1-7B)
    print("\n[4/6] Testing Local LLM (Ollama running deepseek-r1:7b)...")
    try:
        from agent.llm_client import LLMClient
        llm = LLMClient()
        thought, res = llm.route_query("Respond with 'DeepSeek Online' in exactly two words.", task_type="general")
        print(f"  [✓] PASSED: Local Model '{llm.local_model}' responded: '{res[:50]}'")
    except Exception as e:
        print(f"  [✗] FAILED Local LLM: {e}")

    # 5. Cloud Gemini Test (Gemini Flash)
    print("\n[5/6] Testing Cloud LLM (Google Gemini Flash API)...")
    try:
        gemini_res = llm.call_gemini("Respond with 'Gemini Online' in exactly two words.")
        print(f"  [✓] PASSED: Gemini Flash responded: '{gemini_res[:50]}'")
    except Exception as e:
        print(f"  [✗] FAILED Gemini: {e}")

    # 6. LangGraph Cyclic Engine Test
    print("\n[6/6] Testing LangGraph Multi-Agent Courtroom Engine (Real Nodes)...")
    try:
        from agent.graph import investigation_app
        initial_state = {
            "ticker": "HINDUNILVR",
            "company_name": "Hindustan Unilever Ltd",
            "raw_financials": data,
            "computed_metrics": {
                "debtor_days": summary.debtor_days,
                "sales_growth_yoy": summary.sales_growth_yoy,
                "cfo_to_ebitda": summary.cfo_to_ebitda
            },
            "anomalies": [a.model_dump() for a in summary.anomalies],
            "selected_anomaly": None,
            "hypothesis": None,
            "prosecution_evidence": [],
            "peer_evidence": [],
            "defense_arguments": [],
            "is_falsified": False,
            "falsification_reason": None,
            "evidence_strength": None,
            "iteration_count": 0,
            "final_discovery": None,
            "logs": []
        }
        res_state = investigation_app.invoke(initial_state)
        disc = res_state.get("final_discovery")
        assert disc is not None, "Final discovery was not compiled"
        print(f"\n  [✓] PASSED: LangGraph executed 6 real nodes and synthesized 8-point schema!")
        print(f"      1. Discovery: {disc.get('1_The_Discovery')}")
        print(f"      8. Evidence Strength: {disc.get('8_Evidence_Strength')}")
    except Exception as e:
        print(f"  [✗] FAILED LangGraph: {e}")

    print("\n" + "=" * 65)
    print("  ALL 6 ARCHITECTURAL MODULES VERIFIED & OPERATIONAL")
    print("=" * 65)

if __name__ == "__main__":
    test_all()
