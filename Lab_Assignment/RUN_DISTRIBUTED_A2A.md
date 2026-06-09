# Run the Full Distributed A2A System

This guide starts the complete Stage 5 distributed system and the browser demo interface.

The agents use the local markdown database under:

```text
data/standardized
```

Retrieved chunks are injected into the Law, Tax, Compliance, Stage 4, and interface demo prompts as grounding context.

## 1. Prerequisites

- Windows PowerShell
- Python virtual environment already created in `.venv`
- Ollama installed and running
- Local model available:

```powershell
ollama list
```

The expected local model is:

```text
qwen2.5:0.5b
```

If missing:

```powershell
ollama pull qwen2.5:0.5b
```

## 2. Go To The Repo Root

Run every command from the parent repo root:

```powershell
cd C:\Users\khoil\sources\repos\vinuni\Batch02-Day9_Multi-Agent_MCP-A2A
```

Do not run from an old nested copy or another virtual environment.

## 3. Install Dependencies

```powershell
uv sync
```

The project reads configuration from `.env`. For local Ollama, it should include:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:0.5b
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=ollama
```

Confirm the local database exists:

```powershell
Get-ChildItem .\data\standardized -Recurse -Filter *.md
```

## 4. Start The Distributed A2A Services

Open five separate PowerShell terminals from the repo root.

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m registry
```

Terminal 2:

```powershell
.\.venv\Scripts\python.exe -m law_agent
```

Terminal 3:

```powershell
.\.venv\Scripts\python.exe -m tax_agent
```

Terminal 4:

```powershell
.\.venv\Scripts\python.exe -m compliance_agent
```

Terminal 5:

```powershell
.\.venv\Scripts\python.exe -m customer_agent
```

Expected ports:

| Service | Port |
|---|---:|
| Registry | 10000 |
| Customer Agent | 10100 |
| Law Agent | 10101 |
| Tax Agent | 10102 |
| Compliance Agent | 10103 |

## 5. Verify With The Test Client

Open another PowerShell terminal from the repo root:

```powershell
.\.venv\Scripts\python.exe test_client.py
```

The `A2AClient is deprecated` warning is harmless. The important part is that a `RESPONSE` block is printed.

Local Ollama can be slow. The client is configured to wait without a read timeout.

## 6. Start The Demo Interface

Open another terminal from the repo root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn demo_ui:app --host 127.0.0.1 --port 8501
```

Open:

```text
http://127.0.0.1:8501
```

The interface includes:

- Stage 4 in-process multi-agent demo
- Stage 5 distributed A2A demo
- Retrieval from `data/standardized` as the local legal/news database
- Service health checks for all A2A services
- Agent timeline, timings, intermediate outputs, and final response

## 7. Troubleshooting

### Port Already In Use

Check port owners:

```powershell
Get-NetTCPConnection -LocalPort 10000,10100,10101,10102,10103 -ErrorAction SilentlyContinue |
  Select-Object LocalPort,State,OwningProcess
```

Map a PID to its command:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId=PID_HERE" |
  Select-Object ProcessId,CommandLine
```

Stop a stale process:

```powershell
Stop-Process -Id PID_HERE -Force
```

### Missing Credentials Error

If you see:

```text
Missing credentials. Please pass an api_key...
```

The process is probably running old OpenRouter-only code or from the wrong folder. Confirm the traceback path points to:

```text
C:\Users\khoil\sources\repos\vinuni\Batch02-Day9_Multi-Agent_MCP-A2A\common\llm.py
```

That file should support `LLM_PROVIDER=ollama`. Also confirm the running command uses:

```text
...\Batch02-Day9_Multi-Agent_MCP-A2A\.venv\Scripts\python.exe
```

### Timeout Or Very Slow Response

Local Ollama may take a long time because the request can involve several LLM calls:

```text
Customer Agent -> Law Agent -> Tax Agent + Compliance Agent -> Aggregator
```

Wait for the response. If it still hangs, restart the five A2A services and make sure only one copy of each service is running.

### Service Health In Interface Shows Offline

Start or restart the missing service. The interface expects:

```text
Registry:          http://localhost:10000
Customer Agent:    http://localhost:10100
Law Agent:         http://localhost:10101
Tax Agent:         http://localhost:10102
Compliance Agent:  http://localhost:10103
```
