import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langgraph.graph import StateGraph, START, END
from agent.state import InvestigationState
from agent.nodes import (
    anomaly_triage_node,
    attacker_node,
    defender_node,
    adjudicator_node,
    reflection_router,
    compiler_node
)


def build_investigation_graph():
    workflow = StateGraph(InvestigationState)

    workflow.add_node("anomaly_triage", anomaly_triage_node)
    workflow.add_node("attacker", attacker_node)
    workflow.add_node("defender", defender_node)
    workflow.add_node("adjudicator", adjudicator_node)
    workflow.add_node("compiler", compiler_node)

    workflow.add_edge(START, "anomaly_triage")
    workflow.add_edge("anomaly_triage", "attacker")
    workflow.add_edge("attacker", "defender")
    workflow.add_edge("defender", "adjudicator")

    workflow.add_conditional_edges(
        "adjudicator",
        reflection_router,
        {
            "loop_back": "anomaly_triage",
            "proceed": "compiler"
        }
    )

    workflow.add_edge("compiler", END)

    return workflow.compile()


investigation_app = build_investigation_graph()
