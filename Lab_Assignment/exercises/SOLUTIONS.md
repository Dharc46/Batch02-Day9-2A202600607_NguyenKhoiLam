# Solutions

## Exercise 2: Tools and Knowledge Base

- Added the `labor_law` entry to `LEGAL_KNOWLEDGE`.
- Implemented `check_statute_of_limitations(case_type: str)`.
- Registered both tools in the `tools` list.
- Added dispatch handling for every returned tool call through `tool_map`.

Run:

```bash
uv run python exercises/exercise_2_tools.py
```

## Exercise 4: Multi-Agent Privacy Agent

- Implemented `privacy_agent`.
- Added conditional routing for `data`, `privacy`, `gdpr`, and `du lieu`.
- Added `privacy_agent` to the graph.
- Connected `privacy_agent` to `aggregate_results`.
- Included `privacy_analysis` in the final aggregation prompt.

Run:

```bash
uv run python exercises/exercise_4_multiagent.py
```
