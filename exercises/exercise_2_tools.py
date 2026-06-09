"""Exercise 2: Add tools and a knowledge base entry."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm


LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages; (2) consequential damages; (3) specific performance; "
            "(4) cover damages. Statute of limitations is typically 4 years (UCC Section 2-725)."
        ),
    },
    {
        "id": "labor_law",
        "keywords": ["lao dong", "sa thai", "hop dong lao dong", "labor", "termination"],
        "text": (
            "Theo Bo luat Lao dong Viet Nam 2019, nguoi su dung lao dong co the don phuong "
            "cham dut hop dong trong cac truong hop: (1) nguoi lao dong thuong xuyen khong "
            "hoan thanh cong viec; (2) bi om dau, tai nan da dieu tri 12 thang chua khoi; "
            "(3) thien tai, hoa hoan; (4) nguoi lao dong du tuoi nghi huu."
        ),
    },
]


@tool
def search_legal_knowledge(query: str) -> str:
    """Search the legal knowledge base."""
    query_lower = query.lower()
    for entry in LEGAL_KNOWLEDGE:
        if any(kw in query_lower for kw in entry["keywords"]):
            return f"[{entry['id']}] {entry['text']}"
    return "Khong tim thay thong tin lien quan."


@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Check the statute of limitations by case type.

    Args:
        case_type: Case type: contract, tort, or property.
    """
    limits = {
        "contract": "4 nam (UCC Section 2-725)",
        "tort": "2-3 nam tuy bang",
        "property": "5 nam",
    }
    return limits.get(case_type.lower(), "Khong xac dinh")


async def main():
    load_dotenv()
    llm = get_llm()

    tools = [search_legal_knowledge, check_statute_of_limitations]
    llm_with_tools = llm.bind_tools(tools)

    question = "Thoi hieu khoi kien vu vi pham hop dong la bao lau?"

    messages = [
        SystemMessage(content="Ban la chuyen gia phap ly. Su dung tools de tra cuu thong tin."),
        HumanMessage(content=question),
    ]

    print(f"Cau hoi: {question}\n")

    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)

    tool_map = {t.name: t for t in tools}
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"Calling tool: {tool_call['name']}")
            tool_result = await tool_map[tool_call["name"]].ainvoke(tool_call["args"])
            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

        final_response = await llm_with_tools.ainvoke(messages)
        print(f"\nResult:\n{final_response.content}")
    else:
        print(f"\nResult:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
