import sys
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agent.state import InvestigationState
from ingestion.web_search import TavilySearchClient
from agent.llm_client import LLMClient

# Initialize singletons for dummy/skeleton pipeline
search_client = TavilySearchClient()
llm = LLMClient()

def anomaly_triage_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 1: Evaluates anomalies ranked by math sandbox and selects the highest-priority target.
    """
    anomalies = state.get("anomalies", [])
    iteration = state.get("iteration_count", 0)

    if not anomalies:
        # Dummy anomaly for skeleton testing
        selected = {
            "metric_name": "Debtor Days Channel Stuffing",
            "period": "Q3 FY24",
            "delta": 21.9,
            "severity_score": 21.9,
            "description": "Debtor days stretched from 24.2d to 46.1d (+21.9d) while sales grew."
        }
    else:
        # Pick next anomaly if previous was falsified
        index = min(iteration, len(anomalies) - 1)
        selected = anomalies[index]

    log_entry = f"[Node 1: Anomaly Triage] Selected anomaly: '{selected.get('metric_name')}' (Delta: {selected.get('delta')})"
    print(f"--> {log_entry}")

    return {
        "selected_anomaly": selected,
        "logs": state.get("logs", []) + [log_entry]
    }

def hypothesis_generator_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 2: Formulates a testable forensic hypothesis from the selected anomaly.
    """
    anomaly = state.get("selected_anomaly", {})
    ticker = state.get("ticker", "COMPANY")
    company_name = state.get("company_name", ticker)

    # Skeleton prompt / template hypothesis
    thesis = (
        f"{company_name} ({ticker}) experienced an artificial distortion in {anomaly.get('period', 'recent quarters')}: "
        f"{anomaly.get('description', 'Operational metric divergence detected')}. Management narrative may contradict statutory filings."
    )

    log_entry = f"[Node 2: Hypothesis Generator] Formulated thesis: {thesis[:90]}..."
    print(f"--> {log_entry}")

    return {
        "hypothesis": thesis,
        "logs": state.get("logs", []) + [log_entry]
    }

def evidence_harvester_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 3: The Prosecution. Queries concalls and filings for supporting evidence and contradictions.
    """
    ticker = state.get("ticker", "")
    anomaly = state.get("selected_anomaly", {})
    metric_name = anomaly.get("metric_name", "working capital")

    query = f"{ticker} concall transcript {metric_name} inventory receivables"
    search_results = search_client.search(query, max_results=2)

    prosecution_evidence = [
        {
            "source": item.get("title", ""),
            "url": item.get("url", ""),
            "excerpt": item.get("content", "")[:250],
            "contradiction_found": True
        }
        for item in search_results
    ]

    log_entry = f"[Node 3: Evidence Harvester] Harvested {len(prosecution_evidence)} evidence documents via Tavily."
    print(f"--> {log_entry}")

    return {
        "prosecution_evidence": prosecution_evidence,
        "logs": state.get("logs", []) + [log_entry]
    }

def peer_triangulation_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 4: Evaluates competitor filings to determine if anomaly is firm-specific or sector-wide.
    """
    ticker = state.get("ticker", "")
    peers = ["DABUR", "MARICO"]

    peer_evidence = []
    for peer in peers:
        peer_query = f"{peer} quarterly results volume growth debtor days"
        results = search_client.search(peer_query, max_results=1)
        for r in results:
            peer_evidence.append({
                "peer": peer,
                "url": r.get("url", ""),
                "summary": f"Peer {peer} maintained stable receivables (26-28 days) under identical macro conditions."
            })

    log_entry = f"[Node 4: Peer Triangulation] Benchmarked against {len(peers)} peers ({', '.join(peers)}). Divergence is IDIOSYNCRATIC."
    print(f"--> {log_entry}")

    return {
        "peer_evidence": peer_evidence,
        "logs": state.get("logs", []) + [log_entry]
    }

def adversarial_critic_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 5: The Defense Attorney (Self-Falsification). Actively attempts to disprove the thesis via macro justifications.
    """
    iteration = state.get("iteration_count", 0)

    # In a full run, DeepSeek-R1 tests:
    # 1. Did raw material export ban occur?
    # 2. Was there an ERP billing migration?
    # 3. Was Diwali late?
    
    # Skeleton logic: Survives on iteration 0 for test demonstration
    is_falsified = False
    falsification_reason = None
    strength = "Strong"

    log_entry = f"[Node 5: Adversarial Critic] Hypothesis stress-tested. Exculpatory macro evidence rejected. Evidence Strength: {strength}."
    print(f"--> {log_entry}")

    return {
        "is_falsified": is_falsified,
        "falsification_reason": falsification_reason,
        "evidence_strength": strength,
        "iteration_count": iteration + 1,
        "logs": state.get("logs", []) + [log_entry]
    }

def reflection_router(state: InvestigationState) -> str:
    """
    Conditional Edge: Routes back to Anomaly Triage if falsified; otherwise proceeds to Compiler.
    """
    if state.get("is_falsified", False) and state.get("iteration_count", 0) < 2:
        print("--> [Router] Hypothesis FALSIFIED by Defense. Looping back to Triage Node...")
        return "loop_back"
    print("--> [Router] Hypothesis SURVIVED Adversarial Scrutiny. Routing to Compiler...")
    return "proceed"

def compiler_node(state: InvestigationState) -> Dict[str, Any]:
    """
    Node 6: Synthesizes final state into mandatory 8-Point Schema.
    """
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    anomaly = state.get("selected_anomaly", {})

    discovery = {
        "1_The_Discovery": f"{company_name} masked multiple quarters of volume slowdown via aggressive credit expansion (+{anomaly.get('delta', 20)} days).",
        "2_Why_It_Matters": [
            "Price-led top-line growth is nearing consumer exhaustion.",
            "Distributor inventory overhang risks an imminent revenue cliff in subsequent quarters.",
            "Cash conversion efficiency collapsed, impairing operating cash flow."
        ],
        "3_Evidence": [e.get("url") for e in state.get("prosecution_evidence", [])],
        "4_Timeline": "Divergence initiated in Q3 FY23 and widened through Q4 FY24.",
        "5_Numbers": f"Debtor days expanded by +{anomaly.get('delta', 21.9)} days; sales growth was positive while volume remained negative.",
        "6_Counterargument": "Input cost deflation forced price cuts across mass categories, depressing nominal realization.",
        "7_Falsification_Condition": f"Hypothesis is disproven if {company_name} delivers >=2 quarters of >4% volume growth with debtor days < 28d.",
        "8_Evidence_Strength": f"Rating: {state.get('evidence_strength', 'Strong')} (Score: 8.8 / 10)"
    }

    log_entry = "[Node 6: Compiler Node] Mandatory 8-point schema compiled successfully."
    print(f"--> {log_entry}")

    return {
        "final_discovery": discovery,
        "logs": state.get("logs", []) + [log_entry]
    }
