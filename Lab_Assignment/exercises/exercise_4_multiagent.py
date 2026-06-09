"""Exercise 4: Add a privacy agent to the multi-agent system."""

import asyncio
import os
import sys
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from common.llm import get_llm


def _last_wins(left: str | None, right: str | None) -> str:
    """Reducer: the newest non-empty value wins."""
    return right if right is not None else (left or "")


class State(TypedDict):
    question: str
    law_analysis: Annotated[str, _last_wins]
    tax_analysis: Annotated[str, _last_wins]
    compliance_analysis: Annotated[str, _last_wins]
    privacy_analysis: Annotated[str, _last_wins]
    final_response: str


def law_agent(state: State) -> dict:
    """General legal analysis agent."""
    llm = get_llm()
    prompt = f"""You are a legal expert. Analyze this question:

{state['question']}

Focus on contracts, civil liability, legal rights, and legal obligations."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"law_analysis": response.content}


def check_routing(state: State) -> list[Send]:
    """Route to specialist agents based on question keywords."""
    question_lower = state["question"].lower()
    tasks = []

    if any(kw in question_lower for kw in ["tax", "irs", "thue"]):
        tasks.append(Send("tax_agent", state))

    if any(kw in question_lower for kw in ["compliance", "sec", "regulation"]):
        tasks.append(Send("compliance_agent", state))

    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "du lieu"]):
        tasks.append(Send("privacy_agent", state))

    return tasks if tasks else [Send("aggregate_results", state)]


def tax_agent(state: State) -> dict:
    """Tax specialist agent."""
    llm = get_llm()
    prompt = f"""You are a tax expert. Analyze tax aspects of this question:

Question: {state['question']}
Legal analysis: {state.get('law_analysis', 'N/A')}

Focus on IRS, tax evasion, penalties, FBAR, and FATCA."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"tax_analysis": response.content}


def compliance_agent(state: State) -> dict:
    """Compliance specialist agent."""
    llm = get_llm()
    prompt = f"""You are a compliance expert. Analyze compliance aspects:

Question: {state['question']}
Legal analysis: {state.get('law_analysis', 'N/A')}

Focus on SEC, SOX, FCPA, AML, and regulatory violations."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"compliance_analysis": response.content}


def privacy_agent(state: State) -> dict:
    """Privacy and GDPR specialist agent."""
    llm = get_llm()
    prompt = f"""You are an expert in GDPR and personal data protection law.

Original question: {state['question']}
Legal analysis: {state.get('law_analysis', 'N/A')}

Analyze privacy, GDPR, data protection, data breach notification, data subject rights,
regulatory penalties, and likely remediation obligations."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"privacy_analysis": response.content}


def aggregate_results(state: State) -> dict:
    """Aggregate outputs from all agents."""
    llm = get_llm()

    sections = []
    if state.get("law_analysis"):
        sections.append(f"LEGAL ANALYSIS:\n{state['law_analysis']}")
    if state.get("tax_analysis"):
        sections.append(f"TAX ANALYSIS:\n{state['tax_analysis']}")
    if state.get("compliance_analysis"):
        sections.append(f"COMPLIANCE ANALYSIS:\n{state['compliance_analysis']}")
    if state.get("privacy_analysis"):
        sections.append(f"PRIVACY/GDPR ANALYSIS:\n{state['privacy_analysis']}")

    combined = "\n\n".join(sections)
    prompt = f"""Synthesize the following analyses into one complete legal report:

{combined}

Original question: {state['question']}

Create a concise, clearly structured report."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"final_response": response.content}


def build_graph():
    """Build the multi-agent graph."""
    graph = StateGraph(State)

    graph.add_node("law_agent", law_agent)
    graph.add_node("tax_agent", tax_agent)
    graph.add_node("compliance_agent", compliance_agent)
    graph.add_node("privacy_agent", privacy_agent)
    graph.add_node("aggregate_results", aggregate_results)

    graph.add_edge(START, "law_agent")
    graph.add_conditional_edges(
        "law_agent",
        check_routing,
        ["tax_agent", "compliance_agent", "privacy_agent", "aggregate_results"],
    )
    graph.add_edge("tax_agent", "aggregate_results")
    graph.add_edge("compliance_agent", "aggregate_results")
    graph.add_edge("privacy_agent", "aggregate_results")
    graph.add_edge("aggregate_results", END)

    return graph.compile()


async def main():
    load_dotenv()
    question = "If a company has a customer data breach, what are the legal and tax consequences?"

    print("=" * 70)
    print("MULTI-AGENT SYSTEM with Privacy Agent")
    print("=" * 70)
    print(f"\nQuestion: {question}\n")
    print("Processing through agents...\n")

    graph = build_graph()
    result = await graph.ainvoke({
        "question": question,
        "law_analysis": "",
        "tax_analysis": "",
        "compliance_analysis": "",
        "privacy_analysis": "",
        "final_response": "",
    })

    print("\n" + "=" * 70)
    print("FINAL RESULT")
    print("=" * 70)
    print(result["final_response"])
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
