import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langgraph.graph import StateGraph, START, END
from agent.state import InvestigationState
from agent.nodes import (
    anomaly_triage_node,
    hypothesis_generator_node,
    evidence_harvester_node,
    peer_triangulation_node,
    adversarial_critic_node,
    reflection_router,
    compiler_node
)

def build_investigation_graph():
    """
    Constructs the cyclic state graph implementing the Courtroom model.
    """
    workflow = StateGraph(InvestigationState)

    # Add Nodes
    workflow.add_node("anomaly_triage", anomaly_triage_node)
    workflow.add_node("hypothesis_generator", hypothesis_generator_node)
    workflow.add_node("evidence_harvester", evidence_harvester_node)
    workflow.add_node("peer_triangulation", peer_triangulation_node)
    workflow.add_node("adversarial_critic", adversarial_critic_node)
    workflow.add_node("compiler", compiler_node)

    # Standard Sequential Edges
    workflow.add_edge(START, "anomaly_triage")
    workflow.add_edge("anomaly_triage", "hypothesis_generator")
    workflow.add_edge("hypothesis_generator", "evidence_harvester")
    workflow.add_edge("evidence_harvester", "peer_triangulation")
    workflow.add_edge("peer_triangulation", "adversarial_critic")

    # Conditional Reflection Loop Edge
    workflow.add_conditional_edges(
        "adversarial_critic",
        reflection_router,
        {
            "loop_back": "anomaly_triage",
            "proceed": "compiler"
        }
    )

    workflow.add_edge("compiler", END)

    return workflow.compile()

# Pre-compiled application instance
investigation_app = build_investigation_graph()

if __name__ == "__main__":
    print("Compiling LangGraph Investigation StateGraph...")
    app = build_investigation_graph()
    print("Graph compiled successfully with reflection cycle!")
