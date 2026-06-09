"""Stage 4: Multi-Agent System (In-Process).

Multiple specialist agents collaborate on one legal question. This version
adds a privacy/GDPR specialist and keyword routing for data breach questions.
"""

import asyncio
import os
import sys
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from common.llm import get_llm


def _last_wins(a: str, b: str) -> str:
    """Reducer: keep the most recently written value."""
    return b if b else a


class LegalState(TypedDict):
    question: str
    law_analysis: str
    tax_result: Annotated[str, _last_wins]
    compliance_result: Annotated[str, _last_wins]
    privacy_result: Annotated[str, _last_wins]
    final_answer: str


async def analyze_law(state: LegalState) -> dict:
    """Lead attorney analyses the general legal aspects."""
    print("\n  [Node: analyze_law] Lead attorney analysing legal aspects...")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a senior corporate litigation attorney specialising in contract law, "
                "tort law, and general business law. Keep your analysis under 200 words."
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: analyze_law] Done ({len(result.content)} chars)")
    return {"law_analysis": result.content}


def route_to_specialists(state: LegalState) -> list[Send]:
    """Dispatch specialist agents in parallel when their keywords match."""
    question_lower = state["question"].lower()
    sends: list[Send] = []

    if any(kw in question_lower for kw in ["tax", "irs", "thue", "fbar", "fatca"]):
        sends.append(Send("call_tax_specialist", state))

    if any(kw in question_lower for kw in ["compliance", "sec", "regulation", "sox", "aml", "fcpa"]):
        sends.append(Send("call_compliance_specialist", state))

    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "du lieu", "breach"]):
        sends.append(Send("call_privacy_specialist", state))

    return sends if sends else [Send("aggregate", state)]


async def call_tax_specialist(state: LegalState) -> dict:
    """Tax specialist sub-agent."""
    print("\n  [Node: call_tax_specialist] Tax specialist starting...")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a specialist tax attorney and CPA. Focus on IRS enforcement, "
                "tax evasion, penalties, FBAR/FATCA, and practical tax exposure. "
                "Keep your response under 200 words."
            )
        ),
        HumanMessage(content=f"Question: {state['question']}\n\nLegal analysis: {state['law_analysis']}"),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: call_tax_specialist] Done ({len(result.content)} chars)")
    return {"tax_result": result.content}


async def call_compliance_specialist(state: LegalState) -> dict:
    """Regulatory compliance specialist sub-agent."""
    print("\n  [Node: call_compliance_specialist] Compliance specialist starting...")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a senior regulatory compliance officer. Focus on SEC, SOX, FCPA, "
                "AML/BSA, corporate governance, regulatory reporting, and remediation. "
                "Keep your response under 200 words."
            )
        ),
        HumanMessage(content=f"Question: {state['question']}\n\nLegal analysis: {state['law_analysis']}"),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: call_compliance_specialist] Done ({len(result.content)} chars)")
    return {"compliance_result": result.content}


async def call_privacy_specialist(state: LegalState) -> dict:
    """Privacy and GDPR specialist sub-agent."""
    print("\n  [Node: call_privacy_specialist] Privacy specialist starting...")
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "You are a privacy and data protection lawyer specialising in GDPR, CCPA, "
                "data breach response, notification duties, data subject rights, and privacy "
                "regulatory penalties. Keep your response under 200 words."
            )
        ),
        HumanMessage(content=f"Question: {state['question']}\n\nLegal analysis: {state['law_analysis']}"),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: call_privacy_specialist] Done ({len(result.content)} chars)")
    return {"privacy_result": result.content}


async def aggregate(state: LegalState) -> dict:
    """Combine specialist analyses into the final answer."""
    print("\n  [Node: aggregate] Combining all specialist analyses...")
    llm = get_llm()

    sections: list[str] = []
    if state.get("law_analysis"):
        sections.append(f"## Legal Analysis\n{state['law_analysis']}")
    if state.get("tax_result"):
        sections.append(f"## Tax Analysis\n{state['tax_result']}")
    if state.get("compliance_result"):
        sections.append(f"## Regulatory Compliance Analysis\n{state['compliance_result']}")
    if state.get("privacy_result"):
        sections.append(f"## Privacy/GDPR Analysis\n{state['privacy_result']}")

    combined = "\n\n---\n\n".join(sections)
    messages = [
        SystemMessage(
            content=(
                "You are senior legal counsel synthesising specialist analyses into a concise, "
                "well-structured response. Avoid redundancy. Keep the final response under 500 words."
            )
        ),
        HumanMessage(content=combined),
    ]
    result = await llm.ainvoke(messages)
    print(f"  [Node: aggregate] Done ({len(result.content)} chars)")
    return {"final_answer": result.content}


def create_graph():
    """Build and compile the multi-agent StateGraph."""
    graph = StateGraph(LegalState)

    graph.add_node("analyze_law", analyze_law)
    graph.add_node("call_tax_specialist", call_tax_specialist)
    graph.add_node("call_compliance_specialist", call_compliance_specialist)
    graph.add_node("call_privacy_specialist", call_privacy_specialist)
    graph.add_node("aggregate", aggregate)

    graph.set_entry_point("analyze_law")
    graph.add_conditional_edges(
        "analyze_law",
        route_to_specialists,
        ["call_tax_specialist", "call_compliance_specialist", "call_privacy_specialist", "aggregate"],
    )
    graph.add_edge("call_tax_specialist", "aggregate")
    graph.add_edge("call_compliance_specialist", "aggregate")
    graph.add_edge("call_privacy_specialist", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


QUESTION = "If a company has a customer data breach and avoids taxes, what are the legal consequences?"


async def main():
    print("=" * 70)
    print("STAGE 4: Multi-Agent System (In-Process)")
    print("=" * 70)
    print()
    print("[Graph topology]")
    print("  analyze_law -> parallel [tax + compliance + privacy] -> aggregate -> END")
    print()
    print(f"Question: {QUESTION}")
    print("-" * 70)

    graph = create_graph()
    result = await graph.ainvoke({
        "question": QUESTION,
        "law_analysis": "",
        "tax_result": "",
        "compliance_result": "",
        "privacy_result": "",
        "final_answer": "",
    })

    print("\n" + "=" * 70)
    print("FINAL ANSWER")
    print("=" * 70)
    print(result["final_answer"])


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
