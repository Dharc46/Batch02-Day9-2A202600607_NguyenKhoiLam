# Lab Solution Day09

## 1. Lab Overview

This submission upgrades the Day08 legal multi-agent project into a Day09 distributed A2A system using a Supervisor - Workers pattern.

The runnable project is located in:

```text
Lab_Assignment/
```

The root project has the same code for local development, but the assignment copy is packaged under `Lab_Assignment` as requested.

## 2. Supervisor - Workers Pattern

The system uses the following agent roles:

| Role | Module | Responsibility |
|---|---|---|
| User-facing supervisor | `customer_agent` | Receives user questions and delegates legal work through A2A |
| Legal supervisor/orchestrator | `law_agent` | Analyzes the question, routes work, and aggregates worker outputs |
| Worker 1 | `tax_agent` | Handles tax law, tax evasion, IRS/penalty exposure |
| Worker 2 | `compliance_agent` | Handles regulatory compliance, SEC/SOX/AML/FCPA/GDPR issues |
| Service registry | `registry` | Allows agents to register and discover each other dynamically |

The required 2-3 worker pattern is satisfied by:

- `tax_agent`
- `compliance_agent`

Stage 4 also includes a privacy/GDPR specialist in the in-process demo.

## 3. Stage 4: In-Process Multi-Agent Demo

Implemented in:

```text
stages/stage_4_multi_agent/main.py
```

Pattern:

```text
analyze_law -> parallel workers -> aggregate
```

The Stage 4 graph uses LangGraph `StateGraph` and `Send` to route work to specialist agents in parallel.

It now also retrieves grounding context from:

```text
data/standardized
```

## 4. Stage 5: Distributed A2A System

Implemented modules:

```text
registry/
customer_agent/
law_agent/
tax_agent/
compliance_agent/
common/
```

Runtime flow:

```text
User/Test Client
  -> Customer Agent
  -> Registry discovery
  -> Law Agent
  -> Tax Agent + Compliance Agent
  -> Law Agent aggregation
  -> Customer Agent response
```

Each agent runs as a separate HTTP service using the A2A SDK.

## 5. Local Database Grounding

The project uses the local markdown database:

```text
data/standardized
```

Retrieval helper:

```text
common/retrieval.py
```

The helper reuses the local hybrid retrieval pipeline from:

```text
src/task9_retrieval_pipeline.py
```

Retrieved chunks are injected into Law, Tax, Compliance, Stage 4, and demo UI prompts.

## 6. Ollama Local LLM Support

Implemented in:

```text
common/llm.py
common/env.py
```

The project supports local Ollama through `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:0.5b
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=ollama
```

## 7. Demo Interface

Implemented in:

```text
demo_ui.py
```

The interface demonstrates:

- Stage 4 in-process multi-agent execution
- Stage 5 distributed A2A execution
- Service health checks
- Agent timeline
- Intermediate outputs
- Final response

Run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn demo_ui:app --host 127.0.0.1 --port 8501
```

Open:

```text
http://127.0.0.1:8501
```

## 8. How To Run The Full Distributed System

Detailed guide:

```text
RUN_DISTRIBUTED_A2A.md
```

Summary:

```powershell
.\.venv\Scripts\python.exe -m registry
.\.venv\Scripts\python.exe -m law_agent
.\.venv\Scripts\python.exe -m tax_agent
.\.venv\Scripts\python.exe -m compliance_agent
.\.venv\Scripts\python.exe -m customer_agent
```

Then test:

```powershell
.\.venv\Scripts\python.exe test_client.py
```

## 9. Completed Checklist

- `Lab-Solution.md` created.
- `Lab_Assignment/` created.
- Full upgraded Day08 code is placed under `Lab_Assignment/`.
- Supervisor - Workers pattern implemented.
- At least two worker agents are implemented.
- Distributed A2A system runs with dynamic registry discovery.
- Local database `data/standardized` is used as grounding context.
- Browser demo interface is included.
