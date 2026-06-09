"""Stage 2: LLM + RAG / Tools

Adds retrieval-augmented generation and tool use to ground LLM responses
in external data. The LLM can now search a legal knowledge base and
calculate damages — but the orchestration is manual (one tool-call loop).
"""

import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# ---------------------------------------------------------------------------
# Simulated legal knowledge base (in production, this would be a vector store)
# ---------------------------------------------------------------------------

LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages — placing the non-breaching party in the position "
            "they would have been in had the contract been performed; (2) consequential damages "
            "for foreseeable losses (Hadley v. Baxendale, 1854); (3) specific performance when "
            "the subject matter is unique; (4) cover damages — the cost of obtaining substitute "
            "performance. The statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "nda_trade_secret",
        "keywords": ["nda", "non-disclosure", "confidential", "trade secret", "agreement"],
        "text": (
            "NDA breaches may trigger both contractual and statutory liability. Under the Defend "
            "Trade Secrets Act (DTSA, 18 U.S.C. § 1836), misappropriation of trade secrets can "
            "result in: (1) injunctive relief; (2) actual damages plus unjust enrichment; "
            "(3) exemplary damages up to 2x actual damages for willful misappropriation; "
            "(4) attorney's fees. State Uniform Trade Secrets Act (UTSA) versions provide "
            "additional remedies. Criminal prosecution is possible under the Economic Espionage "
            "Act (18 U.S.C. § 1832) with penalties up to $5M for individuals."
        ),
    },
    {
        "id": "dtsa_details",
        "keywords": ["dtsa", "federal", "trade secret", "defend", "statute"],
        "text": (
            "The Defend Trade Secrets Act (2016) created a federal private cause of action for "
            "trade secret misappropriation. Key provisions: (1) ex parte seizure orders in "
            "extraordinary circumstances; (2) 3-year statute of limitations; (3) immunity for "
            "whistleblower disclosures to government officials; (4) employers must notify "
            "employees of whistleblower immunity in any NDA or employment agreement."
        ),
    },
    {
        "id": "liquidated_damages",
        "keywords": ["liquidated", "damages", "penalty", "clause", "contract", "nda"],
        "text": (
            "Liquidated damages clauses in NDAs are enforceable if: (1) actual damages would be "
            "difficult to calculate at the time of contracting; (2) the stipulated amount is a "
            "reasonable estimate of anticipated harm. Courts will void clauses that function as "
            "penalties (Restatement (Second) of Contracts § 356). Typical NDA liquidated damages "
            "range from $10,000 to $500,000 depending on the nature of the confidential information."
        ),
    },
    {
        "id": "injunctive_relief",
        "keywords": ["injunction", "restraining", "order", "equitable", "nda", "breach"],
        "text": (
            "Courts routinely grant temporary restraining orders (TROs) and preliminary injunctions "
            "for NDA breaches because: (1) confidential information, once disclosed, cannot be "
            "'un-disclosed' — making monetary damages inadequate; (2) irreparable harm is presumed "
            "for trade secret misappropriation in many jurisdictions. The movant must show "
            "likelihood of success on the merits, irreparable harm, balance of equities, and "
            "public interest (Winter v. Natural Resources Defense Council, 2008)."
        ),
    },
    {
        "id": "labor_law",
        "keywords": ["lao dong", "sa thai", "hop dong lao dong", "labor", "termination"],
        "text": (
            "Theo Bo luat Lao dong Viet Nam 2019, nguoi su dung lao dong co the don phuong "
            "cham dut hop dong trong mot so truong hop nhu nguoi lao dong thuong xuyen khong "
            "hoan thanh cong viec, om dau/tai nan da dieu tri dai ngay chua khoi, thien tai "
            "hoa hoan, hoac nguoi lao dong du tuoi nghi huu."
        ),
    },
]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_legal_database(query: str) -> str:
    """Search the legal knowledge base for relevant statutes, case law, and legal principles."""
    query_words = set(query.lower().split())
    scored = []
    for entry in LEGAL_KNOWLEDGE:
        overlap = len(query_words & set(entry["keywords"]))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:2]
    if not top:
        return "No relevant legal sources found for this query."
    results = []
    for _, entry in top:
        results.append(f"[{entry['id']}] {entry['text']}")
    return "\n\n".join(results)


@tool
def calculate_damages(breach_type: str, contract_value: float) -> str:
    """Calculate estimated damages for a contract breach based on type and contract value."""
    breach_type_lower = breach_type.lower()
    if "willful" in breach_type_lower or "intentional" in breach_type_lower:
        multiplier = 2.0
        label = "Willful/intentional breach (2x multiplier under DTSA)"
    elif "negligent" in breach_type_lower:
        multiplier = 1.0
        label = "Negligent breach (1x actual damages)"
    else:
        multiplier = 1.5
        label = "Standard breach (1.5x estimated multiplier)"

    base_damages = contract_value * multiplier
    attorney_fees = contract_value * 0.15
    total = base_damages + attorney_fees

    return (
        f"Damage Estimate:\n"
        f"  Breach type: {label}\n"
        f"  Contract value: ${contract_value:,.2f}\n"
        f"  Estimated damages: ${base_damages:,.2f}\n"
        f"  Attorney's fees (~15%): ${attorney_fees:,.2f}\n"
        f"  Total estimated exposure: ${total:,.2f}"
    )


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Check statute of limitations by case type.

    Args:
        case_type: Case type: contract, tort, or property.
    """
    limits = {
        "contract": "4 years (UCC Section 2-725)",
        "tort": "2-3 years depending on state law",
        "property": "5 years",
    }
    return limits.get(case_type.lower(), "Unknown limitation period")


TOOLS = [search_legal_database, calculate_damages, check_statute_of_limitations]

QUESTION = "What are the legal consequences if a company breaches a non-disclosure agreement?"


def _extract_json_object(text: str) -> dict | None:
    """Extract the first JSON object from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _args_for_tool(name: str, question: str) -> dict:
    """Build stable demo arguments for a selected tool."""
    if name == "search_legal_database":
        return {"query": question}
    if name == "calculate_damages":
        return {"breach_type": "willful NDA breach", "contract_value": 100000}
    if name == "check_statute_of_limitations":
        return {"case_type": "contract"}
    return {}


async def plan_tool_calls_with_text_llm(llm, question: str) -> list[tuple[str, dict]]:
    """Ask non-function-calling local models to choose tools as plain JSON."""
    planner_messages = [
        SystemMessage(
            content=(
                "You are a tool planner. Choose tools for the legal question. "
                "Return ONLY valid JSON and no prose. Schema:\n"
                '{"tool_calls":[{"name":"search_legal_database","args":{"query":"..."}},'
                '{"name":"calculate_damages","args":{"breach_type":"...","contract_value":100000}},'
                '{"name":"check_statute_of_limitations","args":{"case_type":"contract"}}]}\n'
                "Available tools:\n"
                "- search_legal_database(query): search statutes, cases, and legal principles.\n"
                "- calculate_damages(breach_type, contract_value): estimate exposure.\n"
                "- check_statute_of_limitations(case_type): check deadline for contract/tort/property."
            )
        ),
        HumanMessage(content=question),
    ]
    planner_response = await llm.ainvoke(planner_messages)
    parsed = _extract_json_object(planner_response.content)
    if not parsed:
        planned_from_text = []
        raw_lower = planner_response.content.lower()
        for tool in TOOLS:
            if tool.name.lower() in raw_lower:
                planned_from_text.append((tool.name, _args_for_tool(tool.name, question)))
        if planned_from_text:
            print("Text planner returned prose; extracted tool names from the LLM plan.")
            print(f"Planner raw output: {planner_response.content[:500]}")
            return planned_from_text

        print("Text planner did not return valid JSON or recognizable tool names.")
        print(f"Planner raw output: {planner_response.content[:500]}")
        return []

    planned_calls = []
    for item in parsed.get("tool_calls", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        args = item.get("args", {})
        if name in {tool.name for tool in TOOLS} and isinstance(args, dict):
            args = args or _args_for_tool(name, question)
            planned_calls.append((name, args))

    return planned_calls


async def plan_tool_calls_with_yes_no_llm(llm, question: str) -> list[tuple[str, dict]]:
    """Use simple yes/no prompts for very small local models."""
    checks = [
        (
            "search_legal_database",
            "Should we search a legal knowledge base before answering this legal question?",
            _args_for_tool("search_legal_database", question),
        ),
        (
            "calculate_damages",
            "Should we estimate possible damages or financial exposure for this NDA breach?",
            _args_for_tool("calculate_damages", question),
        ),
        (
            "check_statute_of_limitations",
            "Should we check the statute of limitations for this contract/NDA breach question?",
            _args_for_tool("check_statute_of_limitations", question),
        ),
    ]

    planned_calls = []
    for name, prompt, args in checks:
        response = await llm.ainvoke([
            SystemMessage(content="Answer with exactly one word: YES or NO."),
            HumanMessage(content=f"Question: {question}\n\n{prompt}"),
        ])
        answer = response.content.strip().upper()
        print(f"  Planner check {name}: {answer[:40]}")
        if answer.startswith("Y"):
            planned_calls.append((name, args))

    return planned_calls


def deterministic_tool_plan(question: str) -> list[tuple[str, dict]]:
    """Last-resort plan if a very small local model cannot plan valid tool calls."""
    return [
        ("search_legal_database", _args_for_tool("search_legal_database", question)),
        ("calculate_damages", _args_for_tool("calculate_damages", question)),
        ("check_statute_of_limitations", _args_for_tool("check_statute_of_limitations", question)),
    ]


def ensure_mandatory_grounding_tools(
    planned_calls: list[tuple[str, dict]],
    question: str,
) -> list[tuple[str, dict]]:
    """Enforce the Stage 2 demo rule that legal answers must be grounded by search."""
    tool_names = {name for name, _ in planned_calls}
    if "search_legal_database" not in tool_names:
        print("  Orchestrator added mandatory search_legal_database grounding tool.")
        return [("search_legal_database", _args_for_tool("search_legal_database", question)), *planned_calls]
    return planned_calls


async def main():
    print("=" * 70)
    print("STAGE 2: LLM + RAG / Tools")
    print("=" * 70)
    print()
    print("[How it works]")
    print("  1. LLM receives tools (search_legal_database, calculate_damages, check_statute_of_limitations)")
    print("  2. LLM decides which tools to call and with what arguments")
    print("  3. We execute the tools and feed results back to the LLM")
    print("  4. LLM generates a final answer grounded in retrieved data")
    print()
    print(f"Question: {QUESTION}")
    print("-" * 70)

    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    tool_map = {t.name: t for t in TOOLS}

    messages = [
        SystemMessage(
            content=(
                "You are a legal expert with access to a legal knowledge base and a damage "
                "calculator. Use the tools provided to ground your analysis in specific statutes "
                "and case law. Always search the database before answering. "
                "Keep your final response under 400 words."
            )
        ),
        HumanMessage(content=QUESTION),
    ]

    # --- Step 1: LLM decides which tools to call ---
    print("\n>>> Step 1: Asking LLM (with tools bound)...\n")
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)

    if not response.tool_calls:
        print(
            "LLM did not return native tool calls. Asking the same LLM to plan tool calls "
            "as JSON for local-model compatibility.\n"
        )
        fallback_calls = await plan_tool_calls_with_text_llm(llm, QUESTION)
        plan_source = "LLM text planner"
        if not fallback_calls:
            print("Retrying tool selection with simple YES/NO prompts for the local model.\n")
            fallback_calls = await plan_tool_calls_with_yes_no_llm(llm, QUESTION)
            plan_source = "LLM YES/NO planner"
        if not fallback_calls:
            fallback_calls = deterministic_tool_plan(QUESTION)
            plan_source = "deterministic last-resort planner"
        else:
            fallback_calls = ensure_mandatory_grounding_tools(fallback_calls, QUESTION)

        print(f">>> Step 2: {plan_source} requested {len(fallback_calls)} tool call(s):\n")
        fallback_results = {}
        for name, args in fallback_calls:
            print(f"  Tool: {name}")
            print(f"  Args: {args}")
            tool_fn = tool_map[name]
            result = await tool_fn.ainvoke(args)
            fallback_results[name] = result
            print(f"  Result: {result[:200]}{'...' if len(result) > 200 else ''}")
            print()
            messages.append(ToolMessage(content=result, tool_call_id=f"fallback_{name}"))

        print(">>> Step 3: Generating final grounded answer with tool results...\n")
        print("Based on the retrieved legal knowledge and calculator tools:")
        print()
        section_number = 1
        if "search_legal_database" in fallback_results:
            print(f"{section_number}. Legal sources:\n{fallback_results['search_legal_database']}")
            print()
            section_number += 1
        if "calculate_damages" in fallback_results:
            print(f"{section_number}. Estimated exposure:\n{fallback_results['calculate_damages']}")
            print()
            section_number += 1
        if "check_statute_of_limitations" in fallback_results:
            print(f"{section_number}. Statute of limitations:\n{fallback_results['check_statute_of_limitations']}")
            print()
        print(
            "Summary: an NDA breach can create contract liability, trade-secret liability, "
            "injunctive relief exposure, damages, attorney-fee exposure, and possible criminal "
            "risk when trade secrets are misappropriated. The example damages calculation is "
            "illustrative only and should be replaced with the real contract value and facts."
        )
        return

    # --- Step 2: Execute tool calls ---
    print(f">>> Step 2: LLM requested {len(response.tool_calls)} tool call(s):\n")
    for tc in response.tool_calls:
        print(f"  Tool: {tc['name']}")
        print(f"  Args: {tc['args']}")

        tool_fn = tool_map[tc["name"]]
        result = await tool_fn.ainvoke(tc["args"])
        print(f"  Result: {result[:200]}{'...' if len(result) > 200 else ''}")
        print()

        messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    # --- Step 3: LLM generates final grounded answer ---
    print(">>> Step 3: LLM generating final answer with tool results...\n")
    final_response = await llm_with_tools.ainvoke(messages)
    print(final_response.content)

    print()
    print("-" * 70)
    print("[Improvements over Stage 1]")
    print("  + Grounded: answers cite specific statutes (DTSA, UCC, etc.)")
    print("  + Tool use: can search databases and calculate damages")
    print("  + More accurate: retrieval reduces hallucination risk")
    print()
    print("[Limitations of Stage 2]")
    print("  - Manual orchestration: we wrote the tool-call loop ourselves")
    print("  - Single pass: only one round of tool calls")
    print("  - No reasoning loop: LLM can't decide to search again if needed")
    print()
    print("Next: Stage 3 wraps this in an autonomous ReAct agent loop.")
    print("=" * 70)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
