r"""Web interface for demonstrating Stage 4 and Stage 5 agent interactions.

Run:
    .venv\Scripts\python -m uvicorn demo_ui:app --reload --port 8501
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from a2a.client import A2AClient
from a2a.types import AgentCard, Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart

from common.a2a_client import _extract_text
from common.env import load_project_env

load_project_env()

app = FastAPI(title="Legal Multi-Agent Demo UI", version="1.0.0")


DEFAULT_QUESTION = (
    "If a company has a customer data breach, breaks a contract, and avoids taxes, "
    "what are the legal and regulatory consequences?"
)


class AskRequest(BaseModel):
    question: str = DEFAULT_QUESTION


@dataclass
class Step:
    id: str
    label: str
    role: str
    status: str
    duration_ms: int | None = None
    output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "role": self.role,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "output": self.output,
        }


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


async def _timed_step(step: Step, func, *args) -> tuple[Step, dict[str, Any]]:
    start = time.perf_counter()
    try:
        result = await func(*args)
        step.status = "done"
        step.duration_ms = _elapsed_ms(start)
        step.output = "\n".join(str(value) for value in result.values() if value)
        return step, result
    except Exception as exc:
        step.status = "failed"
        step.duration_ms = _elapsed_ms(start)
        step.output = str(exc)
        raise


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML


@app.get("/api/services")
async def services() -> dict[str, Any]:
    endpoints = {
        "Registry": "http://localhost:10000/health",
        "Customer Agent": "http://localhost:10100/.well-known/agent.json",
        "Law Agent": "http://localhost:10101/.well-known/agent.json",
        "Tax Agent": "http://localhost:10102/.well-known/agent.json",
        "Compliance Agent": "http://localhost:10103/.well-known/agent.json",
    }
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in endpoints.items():
            started = time.perf_counter()
            try:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
                results.append(
                    {
                        "name": name,
                        "status": "online",
                        "latency_ms": _elapsed_ms(started),
                        "detail": payload.get("name") or payload.get("status") or "ok",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "name": name,
                        "status": "offline",
                        "latency_ms": None,
                        "detail": str(exc),
                    }
                )
    return {"services": results}


@app.post("/api/stage4")
async def run_stage4(request: AskRequest) -> dict[str, Any]:
    from stages.stage_4_multi_agent.main import (
        aggregate,
        analyze_law,
        call_compliance_specialist,
        call_privacy_specialist,
        call_tax_specialist,
        route_to_specialists,
    )

    state: dict[str, Any] = {
        "question": request.question,
        "law_analysis": "",
        "tax_result": "",
        "compliance_result": "",
        "privacy_result": "",
        "final_answer": "",
    }

    steps: list[Step] = [
        Step("client", "Client Request", "User submits legal question", "done", 0, request.question),
        Step("lead", "Lead Legal Agent", "Analyzes base contract and business-law exposure", "running"),
    ]

    lead_step, lead_result = await _timed_step(steps[-1], analyze_law, state)
    state.update(lead_result)

    route_start = time.perf_counter()
    sends = route_to_specialists(state)
    selected_nodes = [send.node for send in sends if send.node != "aggregate"]
    route_output = ", ".join(selected_nodes) if selected_nodes else "No specialist keywords matched"
    steps.append(
        Step(
            "router",
            "Router",
            "Chooses specialist agents from question keywords",
            "done",
            _elapsed_ms(route_start),
            route_output,
        )
    )

    specialist_map = {
        "call_tax_specialist": (
            Step("tax", "Tax Specialist", "IRS, evasion, penalties, FBAR/FATCA", "running"),
            call_tax_specialist,
        ),
        "call_compliance_specialist": (
            Step("compliance", "Compliance Specialist", "SEC, SOX, AML, FCPA, governance", "running"),
            call_compliance_specialist,
        ),
        "call_privacy_specialist": (
            Step("privacy", "Privacy Specialist", "GDPR, breach response, notification duties", "running"),
            call_privacy_specialist,
        ),
    }

    specialist_tasks = [
        _timed_step(specialist_map[node][0], specialist_map[node][1], state)
        for node in selected_nodes
        if node in specialist_map
    ]
    if specialist_tasks:
        for step, result in await asyncio.gather(*specialist_tasks):
            steps.append(step)
            state.update(result)

    aggregate_step = Step("aggregate", "Aggregator", "Synthesizes specialist outputs into one answer", "running")
    aggregate_step, aggregate_result = await _timed_step(aggregate_step, aggregate, state)
    steps.append(aggregate_step)
    state.update(aggregate_result)

    return {
        "mode": "stage4",
        "question": request.question,
        "steps": [step.to_dict() for step in steps],
        "answer": state.get("final_answer", ""),
    }


@app.post("/api/stage5")
async def run_stage5(request: AskRequest) -> dict[str, Any]:
    steps = [
        Step("client", "Client", "Sends A2A message to Customer Agent", "done", 0, request.question),
        Step("customer", "Customer Agent", "Classifies request and delegates to Law Agent", "running"),
        Step("law", "Law Agent", "Orchestrates legal analysis and specialist delegation", "pending"),
        Step("tax", "Tax Agent", "Handles tax exposure when needed", "pending"),
        Step("compliance", "Compliance Agent", "Handles regulatory compliance when needed", "pending"),
        Step("response", "A2A Response", "Returns the final task artifact", "pending"),
    ]

    started = time.perf_counter()
    try:
        answer = await _send_to_customer_agent(request.question)
        total_ms = _elapsed_ms(started)
        for step in steps[1:]:
            step.status = "done"
        steps[1].duration_ms = total_ms
        steps[-1].duration_ms = total_ms
        steps[-1].output = answer
        return {
            "mode": "stage5",
            "question": request.question,
            "steps": [step.to_dict() for step in steps],
            "answer": answer,
        }
    except Exception as exc:
        steps[1].status = "failed"
        steps[1].duration_ms = _elapsed_ms(started)
        steps[1].output = str(exc)
        return {
            "mode": "stage5",
            "question": request.question,
            "steps": [step.to_dict() for step in steps],
            "answer": "",
            "error": str(exc),
        }


async def _send_to_customer_agent(question: str) -> str:
    endpoint = "http://localhost:10100"
    async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as http_client:
        card_resp = await http_client.get(f"{endpoint}/.well-known/agent.json")
        card_resp.raise_for_status()
        agent_card = AgentCard.model_validate(card_resp.json())
        client = A2AClient(httpx_client=http_client, agent_card=agent_card)

        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=question))],
            message_id=str(uuid4()),
        )
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )
        response = await client.send_message(request, http_kwargs={"timeout": None})
        text = _extract_text(response)
        return text or "No text response was returned."


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Legal Multi-Agent Demo</title>
  <style>
    :root {
      --bg: #f7f8fb;
      --ink: #172033;
      --muted: #647087;
      --line: #d8deea;
      --panel: #ffffff;
      --blue: #2563eb;
      --green: #16835f;
      --amber: #a16207;
      --red: #b42318;
      --violet: #6d4aff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      padding: 18px 24px 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    h1 { margin: 0; font-size: 22px; font-weight: 720; }
    .sub { margin-top: 5px; color: var(--muted); font-size: 13px; }
    main {
      display: grid;
      grid-template-columns: minmax(330px, 410px) 1fr;
      min-height: calc(100vh - 73px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #fff;
      padding: 18px;
    }
    section { padding: 18px 22px 28px; }
    label { display: block; font-size: 12px; font-weight: 700; color: var(--muted); margin-bottom: 7px; }
    textarea {
      width: 100%;
      min-height: 155px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: inherit;
      line-height: 1.45;
      color: var(--ink);
    }
    .mode {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin: 14px 0;
    }
    .mode button, .run, .refresh {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      min-height: 38px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }
    .mode button.active {
      background: #eaf1ff;
      border-color: #9ebcff;
      color: #174ea6;
    }
    .run {
      width: 100%;
      background: var(--blue);
      color: white;
      border-color: var(--blue);
      margin-top: 6px;
    }
    .refresh { width: 100%; margin-top: 12px; }
    .services {
      margin-top: 18px;
      border-top: 1px solid var(--line);
      padding-top: 16px;
    }
    .svc {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 7px 0;
      border-bottom: 1px solid #edf0f6;
      font-size: 13px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 72px;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 700;
    }
    .online { color: var(--green); background: #e8f6ef; }
    .offline { color: var(--red); background: #fdebea; }
    .topology {
      display: grid;
      grid-template-columns: repeat(6, minmax(110px, 1fr));
      gap: 10px;
      align-items: stretch;
      margin-bottom: 18px;
    }
    .node {
      min-height: 82px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 11px;
      position: relative;
    }
    .node:after {
      content: "";
      position: absolute;
      right: -10px;
      top: 50%;
      width: 10px;
      border-top: 2px solid var(--line);
    }
    .node:last-child:after { display: none; }
    .node strong { display: block; font-size: 13px; margin-bottom: 5px; }
    .node span { color: var(--muted); font-size: 12px; line-height: 1.35; }
    .node.done { border-color: #9fd8c1; background: #fbfffd; }
    .node.running { border-color: #f4c96f; background: #fffaf0; }
    .node.failed { border-color: #f2aaa5; background: #fff8f7; }
    .workspace {
      display: grid;
      grid-template-columns: minmax(280px, 440px) 1fr;
      gap: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel h2 {
      margin: 0;
      padding: 13px 14px;
      font-size: 15px;
      border-bottom: 1px solid var(--line);
    }
    .step {
      padding: 12px 14px;
      border-bottom: 1px solid #edf0f6;
    }
    .step:last-child { border-bottom: 0; }
    .step-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }
    .step-title { font-weight: 720; font-size: 14px; }
    .step-role { color: var(--muted); font-size: 12px; margin-top: 4px; line-height: 1.35; }
    .step-output {
      margin-top: 9px;
      white-space: pre-wrap;
      color: #263247;
      font-size: 12px;
      line-height: 1.45;
      max-height: 150px;
      overflow: auto;
      background: #f8fafc;
      border: 1px solid #edf0f6;
      border-radius: 6px;
      padding: 9px;
    }
    .answer {
      white-space: pre-wrap;
      line-height: 1.55;
      padding: 15px;
      min-height: 360px;
    }
    .statusline {
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 12px;
    }
    @media (max-width: 980px) {
      main, .workspace { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .topology { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .node:after { display: none; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Legal Multi-Agent Interaction Demo</h1>
    <div class="sub">Stage 4 in-process orchestration and Stage 5 distributed A2A routing</div>
  </header>
  <main>
    <aside>
      <label for="question">Question</label>
      <textarea id="question"></textarea>
      <div class="mode">
        <button id="stage4" class="active" type="button">Stage 4</button>
        <button id="stage5" type="button">Stage 5</button>
      </div>
      <button class="run" id="run" type="button">Run Demo</button>
      <button class="refresh" id="refresh" type="button">Refresh Services</button>
      <div class="services">
        <label>Stage 5 Services</label>
        <div id="services"></div>
      </div>
    </aside>
    <section>
      <p class="statusline" id="status">Ready.</p>
      <div class="topology" id="topology"></div>
      <div class="workspace">
        <div class="panel">
          <h2>Agent Timeline</h2>
          <div id="steps"></div>
        </div>
        <div class="panel">
          <h2>Final Response</h2>
          <div class="answer" id="answer">Run a demo to see the response.</div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const defaultQuestion = "If a company has a customer data breach, breaks a contract, and avoids taxes, what are the legal and regulatory consequences?";
    const question = document.getElementById("question");
    const run = document.getElementById("run");
    const refresh = document.getElementById("refresh");
    const statusLine = document.getElementById("status");
    const stepsEl = document.getElementById("steps");
    const answerEl = document.getElementById("answer");
    const topologyEl = document.getElementById("topology");
    const servicesEl = document.getElementById("services");
    const stage4 = document.getElementById("stage4");
    const stage5 = document.getElementById("stage5");
    let mode = "stage4";

    question.value = defaultQuestion;

    const topologies = {
      stage4: [
        ["Client", "Question"],
        ["Lead Legal", "Base analysis"],
        ["Router", "Keyword dispatch"],
        ["Specialists", "Parallel work"],
        ["Aggregator", "Synthesis"],
        ["Answer", "Final output"]
      ],
      stage5: [
        ["Client", "A2A message"],
        ["Customer", "Entry point"],
        ["Registry", "Discovery"],
        ["Law", "Orchestrator"],
        ["Tax + Compliance", "Distributed agents"],
        ["Answer", "Task artifact"]
      ]
    };

    function setMode(next) {
      mode = next;
      stage4.classList.toggle("active", next === "stage4");
      stage5.classList.toggle("active", next === "stage5");
      renderTopology([]);
    }

    function renderTopology(doneIds) {
      topologyEl.innerHTML = "";
      topologies[mode].forEach(([name, role], index) => {
        const node = document.createElement("div");
        node.className = "node" + (doneIds.length ? " done" : "");
        node.innerHTML = `<strong>${name}</strong><span>${role}</span>`;
        topologyEl.appendChild(node);
      });
    }

    function badge(status) {
      const klass = status === "done" || status === "online" ? "online" :
        status === "failed" || status === "offline" ? "offline" : "";
      return `<span class="badge ${klass}">${status}</span>`;
    }

    function renderSteps(steps) {
      stepsEl.innerHTML = "";
      steps.forEach(step => {
        const item = document.createElement("div");
        item.className = "step";
        const time = step.duration_ms === null || step.duration_ms === undefined ? "" : `${step.duration_ms} ms`;
        item.innerHTML = `
          <div class="step-head">
            <div>
              <div class="step-title">${step.label}</div>
              <div class="step-role">${step.role}</div>
            </div>
            <div>${badge(step.status)} ${time}</div>
          </div>
          ${step.output ? `<div class="step-output">${escapeHtml(step.output)}</div>` : ""}
        `;
        stepsEl.appendChild(item);
      });
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;"
      }[ch]));
    }

    async function loadServices() {
      servicesEl.innerHTML = "Checking...";
      const response = await fetch("/api/services");
      const data = await response.json();
      servicesEl.innerHTML = "";
      data.services.forEach(svc => {
        const row = document.createElement("div");
        row.className = "svc";
        const latency = svc.latency_ms === null ? "" : ` (${svc.latency_ms} ms)`;
        row.innerHTML = `<span>${svc.name}<br><small>${escapeHtml(svc.detail)}${latency}</small></span>${badge(svc.status)}`;
        servicesEl.appendChild(row);
      });
    }

    async function runDemo() {
      run.disabled = true;
      statusLine.textContent = mode === "stage4"
        ? "Running Stage 4 in-process graph..."
        : "Calling Stage 5 Customer Agent over A2A...";
      answerEl.textContent = "Waiting for agent response...";
      stepsEl.innerHTML = "";
      renderTopology([]);
      try {
        const response = await fetch(`/api/${mode}`, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question: question.value})
        });
        const data = await response.json();
        renderSteps(data.steps || []);
        answerEl.textContent = data.answer || data.error || "No answer returned.";
        statusLine.textContent = data.error ? "Demo failed." : "Demo completed.";
        renderTopology((data.steps || []).filter(s => s.status === "done").map(s => s.id));
        await loadServices();
      } catch (error) {
        statusLine.textContent = "Demo failed.";
        answerEl.textContent = String(error);
      } finally {
        run.disabled = false;
      }
    }

    stage4.addEventListener("click", () => setMode("stage4"));
    stage5.addEventListener("click", () => setMode("stage5"));
    run.addEventListener("click", runDemo);
    refresh.addEventListener("click", loadServices);
    renderTopology([]);
    loadServices();
  </script>
</body>
</html>"""
