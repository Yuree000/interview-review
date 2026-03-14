from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from part_b.nodes.context_completer import complete_context
from part_b.nodes.qa_pairer import build_qa_pairs
from part_b.nodes.role_identifier import identify_roles
from part_b.state import Phase3State


def _b1_node(state: Phase3State) -> Phase3State:
    role_result, transcription = identify_roles(
        state["transcription"],
        meta=state.get("meta"),
        resume=state.get("resume_profile"),
    )
    return {
        "transcription": transcription,
        "role_result": role_result.model_dump(mode="json"),
    }


def _b2_node(state: Phase3State) -> Phase3State:
    context_result, meta = complete_context(
        state["transcription"],
        meta=state["meta"],
        resume=state.get("resume_profile"),
    )
    return {
        "meta": meta,
        "context_result": context_result.model_dump(mode="json"),
    }


def _b3_node(state: Phase3State) -> Phase3State:
    qa_pairs = build_qa_pairs(
        state["transcription"],
        meta=state.get("meta"),
    )
    return {"qa_pairs": qa_pairs}


def build_phase3_graph():
    graph = StateGraph(Phase3State)
    graph.add_node("b1_role_identifier", _b1_node)
    graph.add_node("b2_context_completer", _b2_node)
    graph.add_node("b3_qa_pairer", _b3_node)
    graph.add_edge(START, "b1_role_identifier")
    graph.add_edge("b1_role_identifier", "b2_context_completer")
    graph.add_edge("b2_context_completer", "b3_qa_pairer")
    graph.add_edge("b3_qa_pairer", END)
    return graph.compile()


def run_phase3_graph(initial_state: Phase3State) -> Phase3State:
    graph = build_phase3_graph()
    return graph.invoke(initial_state)
